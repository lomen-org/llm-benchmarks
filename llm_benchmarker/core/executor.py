import asyncio
import time
import aiohttp
from ..utils import env_loader # Keep env_loader for fallback
import copy
from typing import List, Dict, Any, Optional
import json

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
    endpoint_url = cfg.get("endpoint_url", env_loader.get_env("BENCHMARK_ENDPOINT_URL"))
    api_key = cfg.get("api_key", env_loader.get_env("BENCHMARK_API_KEY"))
    model_name = cfg.get("model", env_loader.get_env("BENCHMARK_MODEL", "gemini-2.0-flash"))

    if not endpoint_url:
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

        async with semaphore:
            start_time = time.perf_counter()
            try:
                async with session.post(endpoint_url, json=payload, headers=headers) as resp:
                    latency = time.perf_counter() - start_time
                    resp_status = resp.status
                    resp_text = await resp.text() # Read text for better error reporting

                    if resp_status != 200:
                        return {
                            **turn_info,
                            "actual": None,
                            "error": f"HTTP {resp_status}: {resp_text}",
                            "latency": latency
                        }

                    try:
                        data = json.loads(resp_text) # Parse JSON from text
                        # Handle potential variations in response structure
                        if not data.get("choices") or not data["choices"][0].get("message"):
                             raise ValueError("Unexpected response structure: 'choices' or 'message' missing.")
                        answer = data["choices"][0]["message"]["content"]
                    except (json.JSONDecodeError, ValueError, KeyError, IndexError) as json_e:
                         return {
                            **turn_info,
                            "actual": None,
                            "error": f"Response parsing error: {json_e} - Response text: {resp_text}",
                            "latency": latency
                        }

                    return {
                        **turn_info,
                        "actual": answer,
                        "latency": latency,
                        "error": None
                    }
            except aiohttp.ClientError as client_e:
                 return {
                    **turn_info,
                    "actual": None,
                    "error": f"Connection error: {client_e}",
                    "latency": time.perf_counter() - start_time # Record latency even on connection error
                }
            except Exception as e:
                # Catch any other unexpected errors during the request
                return {
                    **turn_info,
                    "actual": None,
                    "error": f"Unexpected execution error: {str(e)}",
                    "latency": time.perf_counter() - start_time
                }

    # Use a single session for all requests
    async with aiohttp.ClientSession() as session:
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


        # Gather results from all tasks (conversations and single prompts)
        task_results = await asyncio.gather(*all_tasks)

        # Flatten the results (since conversations return lists of results)
        for res_item in task_results:
            if isinstance(res_item, list):
                results.extend(res_item)
            else:
                results.append(res_item)

    return results
