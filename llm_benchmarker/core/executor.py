import asyncio
import time
import aiohttp
from aiohttp import ClientTimeout
from ..utils import env_loader # Keep env_loader for fallback
import copy
from typing import List, Dict, Any, Optional
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_prompts(
    prompts_or_conversations: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Runs prompts or conversations against a specified LLM endpoint.

    Args:
        prompts_or_conversations: A list of prompt or conversation dictionaries.
        config: An optional dictionary containing configuration like:
            batch_size: Max concurrent requests.
            request_delay_ms: Delay in milliseconds between requests within a batch (default 0).
            max_retries: Maximum number of retries on 429 errors (default 3).
            endpoint_url: The API endpoint URL.
            api_key: The API key.
            model: The model name to use.
            headers: Optional additional headers.

    Returns:
        A list of result dictionaries for each turn/prompt.
    """
    cfg = config or {}
    # Use config values or fallback to environment variables
    batch_size = int(cfg.get("batch_size", env_loader.get_env("BATCH_SIZE", 5)))
    request_delay_ms = int(cfg.get("request_delay_ms", env_loader.get_env("REQUEST_DELAY_MS", 0)))
    max_retries = int(cfg.get("max_retries", env_loader.get_env("MAX_RETRIES", 3)))
    endpoint_url = cfg.get("endpoint_url", env_loader.get_env("BENCHMARK_ENDPOINT_URL"))
    api_key = cfg.get("api_key", env_loader.get_env("BENCHMARK_API_KEY"))
    model_name = cfg.get("model", env_loader.get_env("BENCHMARK_MODEL", "gemini-2.0-flash"))

    logger.info(f"Starting execution: BatchSize={batch_size}, Delay={request_delay_ms}ms, Retries={max_retries}, Model={model_name}, Endpoint={endpoint_url}")
    if not endpoint_url:
        logger.error("Endpoint URL is missing.")
        raise ValueError("Endpoint URL must be provided either in config or BENCHMARK_ENDPOINT_URL env var.")

    semaphore = asyncio.Semaphore(batch_size)

    # Prepare headers
    headers = {"Content-Type": "application/json", **cfg.get("headers", {})}
    if api_key and "x-bearer-token" not in headers and "Authorization" not in headers : # Avoid overriding custom auth
        headers["Authorization"] = f"Bearer {api_key}" # Use standard Authorization header
        headers["x-bearer-token"] = api_key # For compatibility with some APIs

    results = []

    async def _run_single_turn(session, payload, turn_info):
        # Ensure the configured model is in the payload
        payload["model"] = model_name
        payload["stream"] = False # Ensure stream is false
        turn_id = turn_info.get("id", "unknown_id") # Get ID for logging
        retries = 0
        last_error = None
        
        await asyncio.sleep(30)

        async with semaphore:
            while retries <= max_retries:
                start_time = time.perf_counter()
                logger.info(f"Attempt {retries + 1}/{max_retries + 1} for item {turn_id}...")
                try:
                    # Make the request
                    async with session.post(endpoint_url, json=payload, headers=headers) as resp:
                        latency = time.perf_counter() - start_time
                        resp_status = resp.status
                        resp_text = await resp.text() # Read text for better error reporting
                        logger.info(f"Received response for item {turn_id} (Attempt {retries + 1}) - Status: {resp_status}, Latency: {latency:.4f}s")

                        if resp_status == 200:
                            # Success path
                            try:
                                data = json.loads(resp_text) # Parse JSON from text
                                if not data.get("choices") or not data["choices"][0].get("message") or "content" not in data["choices"][0]["message"]:
                                     err_msg = "Unexpected response structure: 'choices', 'message', or 'content' missing."
                                     logger.error(f"Parsing error for item {turn_id}: {err_msg} - Response: {resp_text[:500]}...")
                                     # Treat parsing error as a failure for this attempt, but don't retry automatically
                                     last_error = f"Response parsing error: {err_msg} - Response text: {resp_text}"
                                     break # Exit retry loop on parsing error

                                answer = data["choices"][0]["message"]["content"]
                                return {
                                    **turn_info,
                                    "actual": answer,
                                    "latency": latency,
                                    "error": None
                                }
                            except (json.JSONDecodeError, ValueError, KeyError, IndexError) as json_e:
                                 logger.error(f"Response parsing error for item {turn_id}: {json_e} - Response: {resp_text[:500]}...")
                                 last_error = f"Response parsing error: {json_e} - Response text: {resp_text}"
                                 break # Exit retry loop on parsing error

                        elif resp_status == 429 and retries < max_retries:
                            # Rate limit error, retry if possible
                            retries += 1
                            # Exponential backoff: 1s, 2s, 4s, ...
                            backoff_time = 2**(retries - 1)
                            logger.warning(f"Rate limit (429) hit for item {turn_id}. Retrying in {backoff_time}s... (Attempt {retries}/{max_retries})")
                            await asyncio.sleep(backoff_time)
                            continue # Go to next iteration of the while loop

                        else:
                            # Other non-200 HTTP error, do not retry
                            logger.error(f"HTTP error for item {turn_id}: Status {resp_status}, Response: {resp_text[:500]}...") # Log truncated response
                            last_error = f"HTTP {resp_status}: {resp_text}"
                            break # Exit retry loop

                except aiohttp.ClientError as client_e:
                     logger.error(f"Connection error for item {turn_id} (Attempt {retries + 1}): {client_e}")
                     last_error = f"Connection error: {client_e}"
                     # Decide if connection errors should be retried (optional, currently not retrying)
                     break # Exit retry loop on connection error

                except Exception as e:
                    # Catch any other unexpected errors during the request
                    logger.error(f"Unexpected execution error for item {turn_id} (Attempt {retries + 1}): {e}", exc_info=True) # Log traceback
                    last_error = f"Unexpected execution error: {str(e)}"
                    break # Exit retry loop on unexpected error

            # If loop finished without returning success, return the last error
            return {
                **turn_info,
                "actual": None,
                "error": last_error or "Max retries reached or non-retryable error occurred.",
                "latency": time.perf_counter() - start_time # Latency of the last attempt
            }

    # Define a longer timeout (e.g., 600 seconds = 10 minutes)
    timeout = ClientTimeout(total=600)


    # Use a single session for all requests with the specified timeout
    async with aiohttp.ClientSession(timeout=timeout) as session:
        all_tasks = [] # Use a single list for all tasks

        for item in prompts_or_conversations:
            if "turns" in item:  # Conversation format
                # Process conversation turns sequentially within the conversation
                # but allow multiple conversations to run concurrently.
                async def _run_conversation(conv_item):
                    conv_results = []
                    conversation_id = conv_item["id"]
                    current_messages = []
                    for i, turn in enumerate(conv_item["turns"]):
                        turn_id = f"{conversation_id}-turn-{i+1}"
                        user_message = {"role": "user", "content": turn["user"]}
                        current_messages.append(user_message)

                        payload = {
                            "messages": copy.deepcopy(current_messages), # Send history
                            # Model and stream are set in _run_single_turn
                        }

                        turn_info = {
                            "id": turn_id,
                            "conversation_id": conversation_id,
                            "turn": i + 1,
                            "user_message": turn["user"],
                            "expected": turn.get("expected"),
                        }

                        # Run the turn and get the result
                        result = await _run_single_turn(session, payload, turn_info)
                        conv_results.append(result)

                        # Add assistant response to history for the next turn
                        if result.get("actual") and not result.get("error"):
                            assistant_message = {"role": "assistant", "content": result["actual"]}
                            current_messages.append(assistant_message)
                        else:
                            # If a turn failed, stop processing this conversation
                            break # Stop processing turns for this conversation
                    return conv_results

                all_tasks.append(_run_conversation(item))

            elif "messages" in item:  # Single prompt format
                payload = {
                    "messages": item["messages"],
                     # Model and stream are set in _run_single_turn
                }
                # Ensure user_message is extracted safely
                user_message_content = ""
                if item.get("messages") and isinstance(item["messages"], list) and len(item["messages"]) > 0:
                    user_message_content = item["messages"][0].get("content", "")

                turn_info = {
                    "id": item["id"],
                    "expected": item.get("expected"),
                    "user_message": user_message_content
                }
                # Schedule the task for concurrent execution
                all_tasks.append(_run_single_turn(session, payload, turn_info))

            else:
                # Handle invalid item format
                results.append({
                    "id": item.get("id", "unknown_id"),
                    "error": "Invalid item format: Missing 'turns' or 'messages' key.",
                    "actual": None,
                    "latency": 0
                })
                logger.warning(f"Skipping invalid item: {item.get('id', 'unknown_id')}. Reason: Missing 'turns' or 'messages'.")


        # Gather results from all tasks (conversations and single prompts)
        logger.info(f"Waiting for {len(all_tasks)} tasks to complete...")
        task_results = await asyncio.gather(*all_tasks)
        logger.info("All execution tasks finished.")

        # Flatten the results (since conversations return lists of results)
        for res_item in task_results:
            if isinstance(res_item, list):
                results.extend(res_item)
            else:
                results.append(res_item)

    return results
