import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from ..utils import env_loader # Keep env_loader for fallback
from typing import List, Dict, Any, Optional
import logging
import time

# Configure logging (can share config with executor or have its own)
# Using the same basic config for simplicity here
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def evaluate_responses(
    results: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Evaluates the responses generated by the executor using an evaluator LLM.

    Args:
        results: A list of result dictionaries from the executor.
        config: An optional dictionary containing configuration like:
            eval_model: The evaluator model name.
            eval_api_key: The API key for the evaluator model.
            eval_endpoint_url: The endpoint URL for the evaluator model.
            eval_batch_size: Max concurrent evaluation requests (default 5).
            eval_request_delay_ms: Delay in milliseconds between evaluation requests (default 0).
            eval_max_retries: Max retries on 429 errors for evaluator (default 3).
            benchmark_api_key: Fallback API key if eval_api_key is missing.
            benchmark_endpoint_url: Fallback endpoint if eval_endpoint_url is missing.

    Returns:
        A list of result dictionaries, augmented with evaluation scores and reasoning.
    """
    logger.info(f"Starting evaluation for {len(results)} items...")
    cfg = config or {}
    # Use config values or fallback to environment variables
    eval_model = cfg.get("eval_model", env_loader.get_env("EVAL_MODEL", "gemini-2.5-flash-preview-04-17"))
    eval_api_key = cfg.get("eval_api_key", env_loader.get_env("EVAL_API_KEY", env_loader.get_env("BENCHMARK_API_KEY")))
    eval_endpoint_url = cfg.get("eval_endpoint_url", env_loader.get_env("EVAL_ENDPOINT_URL", env_loader.get_env("BENCHMARK_ENDPOINT_URL")))
    eval_batch_size = int(cfg.get("eval_batch_size", env_loader.get_env("EVAL_BATCH_SIZE", 5)))
    eval_request_delay_ms = int(cfg.get("eval_request_delay_ms", env_loader.get_env("EVAL_REQUEST_DELAY_MS", 0)))
    eval_max_retries = int(cfg.get("eval_max_retries", env_loader.get_env("EVAL_MAX_RETRIES", 3)))
    logger.info(f"Evaluator Config: Model={eval_model}, Endpoint={eval_endpoint_url}, BatchSize={eval_batch_size}, Delay={eval_request_delay_ms}ms, Retries={eval_max_retries}")

    if not eval_api_key:
        logger.warning("Evaluator API key not found in config or environment variables (EVAL_API_KEY, BENCHMARK_API_KEY). Evaluation might fail.")
    if not eval_endpoint_url:
         logger.warning("Evaluator endpoint URL not found in config or environment variables (EVAL_ENDPOINT_URL, BENCHMARK_ENDPOINT_URL). Evaluation might fail.")
         # Allow proceeding without endpoint if user intends to use default OpenAI endpoint

    try:
        logger.info(f"Initializing evaluator LLM: {eval_model}")

        evaluator = ChatGoogleGenerativeAI(
            model=eval_model,
            google_api_key=eval_api_key,
            temperature=0.5,
        )
        logger.info("Evaluator LLM initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing evaluator LLM: {e}", exc_info=True)
        # Return results without evaluation if evaluator fails to initialize
        return [ {**r, "score": None, "scoreReasoning": None, "eval_error": f"Evaluator Initialization Error: {e}"} for r in results]


    semaphore = asyncio.Semaphore(eval_batch_size)

    async def _evaluate(item):
        # Extract relevant info from the result item
        prompt_content = item.get("user_message", item.get("prompt", "")) # Handle both keys
        expected_answer = item.get("expected")
        actual_answer = item.get("actual")
        item_id = item.get("id")

        # Handle cases where the execution failed or actual answer is missing
        # Also skip evaluation if there's already an error from the executor
        if item.get("error"):
            reason_skip = f"Execution error occurred: {item.get('error')}"
            logger.warning(f"Skipping evaluation for item {item_id}: {reason_skip}")
            return {
                **item, # Keep original fields
                "id": item_id,
                "prompt": prompt_content,
                "expected": expected_answer,
                "actual": actual_answer, # Keep actual as None if it was None
                "score": None, # Score is None because evaluation was skipped due to prior error
                "scoreReasoning": f"Evaluation skipped: {reason_skip}.",
                "eval_error": None # No *evaluation* error here, the error was during execution
            }
        elif actual_answer is None:
             reason_skip = "No actual answer generated"
             logger.warning(f"Skipping evaluation for item {item_id}: {reason_skip}")
             return {
                 **item, # Keep original fields
                 "id": item_id,
                 "prompt": prompt_content,
                 "expected": expected_answer,
                 "actual": actual_answer,
                 "score": 0.0, # Assign 0 score for no answer
                 "scoreReasoning": f"Evaluation skipped: {reason_skip}.",
                 "eval_error": "No actual answer generated by the benchmarked model." # Add specific error
             }

        # Build evaluation prompt dynamically based on presence of expected answer
        try:
            if expected_answer:
                content = (
                    f"Reference answer:\n{expected_answer}\n\n"
                    f"Actual answer:\n{actual_answer}\n\n"
                    "Your task is to act as a strict evaluator comparing the actual answer to the reference answer.\n"
                    "Context: This might be part of a conversation.\n"
                    "✅ Focus on semantic similarity, not exact match.\n"
                    "✅ Variable values, numbers, or identifiers may vary, as long as meaning is preserved.\n"
                    "✅ Check if the actual answer delivers the same intent, logic, and meaning as the reference.\n"
                    "✅ Ignore formatting differences or phrasing variations.\n"
                    "❌ Deduct points if meaning is lost, logic is incorrect, or important elements are missing.\n"
                    "❌ **CRITICAL: Assign a score of 0.0** if the actual answer indicates *any* inability, failure, error, or refusal to answer. Examples include, but are not limited to: 'I couldn't retrieve', 'Unable to fetch', 'I don't know', 'Error', 'wasn't able to run', 'I encountered an error', 'failed to', 'cannot provide', 'request failed'. Be very strict about this.\n\n"
                    "Respond with:\n"
                    "1. A **single numeric score between 0 and 1**, with up to two decimal places.\n"
                    "2. Followed by a short reason for this score, in **one sentence**.\n\n"
                    "Format your response exactly like this:\n"
                    "0.85\nReason: The actual answer matches the intent but misses some details.\n\n"
                    "**Special case for 0.0 score due to inability/refusal:**\n"
                    "If you assign 0.0 because the answer indicates inability or refusal, format the response like this:\n"
                    "0.0\nReason: Inability: The model stated it could not perform the task.\n\n"
                    "Important: Do not add any other explanation outside this format."
                )
            else:
                # Self-evaluation if no expected answer is provided
                content = (
                    f"Actual answer:\n{actual_answer}\n\n"
                    "There is no reference answer provided.\n"
                    "Your task is to self-evaluate this answer for correctness, completeness, and clarity.\n"
                    "Context: This might be part of a conversation.\n"
                    "✅ Consider if the answer is logically sound and factually correct.\n"
                    "✅ Check if it fully answers the implied question or task.\n"
                    "✅ Reward answers that are well-structured, clear, and comprehensive.\n"
                    "❌ Deduct points for incomplete, vague, or factually incorrect responses.\n"
                    "❌ **CRITICAL: Assign a score of 0.0** if the actual answer indicates *any* inability, failure, error, or refusal to answer. Examples include, but are not limited to: 'I couldn't retrieve', 'Unable to fetch', 'I don't know', 'Error', 'wasn't able to run', 'I encountered an error', 'failed to', 'cannot provide', 'request failed'. Be very strict about this.\n\n"
                    "Respond with:\n"
                    "1. A **single numeric score between 0 and 1**, with up to two decimal places.\n"
                    "2. Followed by a short reason for this score, in **one sentence**.\n\n"
                    "Format your response exactly like this:\n"
                    "0.90\nReason: The answer is clear, well-explained, and complete.\n\n"
                    "**Special case for 0.0 score due to inability/refusal:**\n"
                    "If you assign 0.0 because the answer indicates inability or refusal, format the response like this:\n"
                    "0.0\nReason: Inability: The model stated it could not perform the task.\n\n"
                    "Important: Do not add any other explanation outside this format."
                )

            eval_prompt_messages = [
                {"role": "system", "content": "You are a strict evaluator of answers."},
                {"role": "user", "content": content}
            ]
            # logger.debug(f"Evaluation prompt for item {item_id}:\n{json.dumps(eval_prompt_messages, indent=2)}") # Optional: Log full prompt if needed (can be verbose)
        except Exception as prompt_build_e:
             # Error building the evaluation prompt itself
             logger.error(f"Error building evaluation prompt for item {item_id}: {prompt_build_e}", exc_info=True)
             return {
                **item,
                "score": None,
                "scoreReasoning": "Evaluation skipped: Error building evaluation prompt.",
                "eval_error": f"Prompt build error: {prompt_build_e}"
            }

        async with semaphore:
            logger.info(f"Sending evaluation request for item {item_id} (using internal retries)...")
            try:
                await asyncio.sleep(30)
                # Use the initialized evaluator instance (internal retries handled by ChatOpenAI)
                start_time = time.perf_counter()
                res = await evaluator.ainvoke(eval_prompt_messages)
                latency = time.perf_counter() - start_time
                raw_response = res.content.strip() if hasattr(res, 'content') else str(res).strip() # Handle different response types
                logger.info(f"Received evaluation response for item {item_id}. Latency: {latency:.4f}s")
                # logger.debug(f"Raw evaluation response for item {item_id}: {raw_response}") # Optional: Log raw response

                score = None
                reason = "Evaluation parsing failed: Could not extract score/reason."
                eval_error = None # Initialize eval_error for this item
                try:
                    lines = raw_response.split("\n", 1)
                    if lines and len(lines) >= 1:
                        score_str = lines[0].strip()
                        # More robust score parsing
                        score_val = float(score_str)
                        score = min(1.0, max(0.0, score_val)) # Clamp score
                        if len(lines) > 1:
                            reason_prefix = "Reason:"
                            reason_line = lines[1].strip()
                            if reason_line.startswith(reason_prefix):
                                reason = reason_line[len(reason_prefix):].strip()
                            else:
                                reason = reason_line # Use the whole line if "Reason:" prefix is missing

                            # Check for inability indication based on score and reason prefix
                            if score == 0.0 and reason.lower().startswith("inability:"):
                                eval_error = f"Evaluator identified inability: {reason}"
                                logger.warning(f"Evaluator assigned 0.0 score for inability for item {item_id}. Reason: {reason}")
                            elif score == 0.0:
                                # Score is 0.0 but reason doesn't start with "Inability:", add generic error
                                eval_error = "Evaluator assigned 0.0 score."
                                logger.warning(f"Evaluator assigned 0.0 score for item {item_id} (reason did not start with 'Inability:'). Reason: {reason}")

                        else:
                            reason = "Score found, but reason missing in evaluator response."
                            if score == 0.0:
                                eval_error = "Evaluator assigned 0.0 score (reason missing)."
                                logger.warning(f"Evaluator assigned 0.0 score for item {item_id}, but reason was missing.")
                    else:
                        # If splitting fails, maybe the whole response is the score?
                        try:
                            score_val = float(raw_response)
                            score = min(1.0, max(0.0, score_val))
                            reason = "Score found, but reason missing in evaluator response."
                            if score == 0.0:
                                eval_error = "Evaluator assigned 0.0 score (reason missing)."
                                logger.warning(f"Evaluator assigned 0.0 score for item {item_id}, but reason was missing.")
                        except ValueError:
                            # If it's not a float either, parsing failed
                            reason = f"Evaluation parsing failed: Unexpected format '{raw_response}'"
                            eval_error = f"Evaluation parsing failed: Unexpected format." # Add parsing error
                            logger.warning(f"Could not parse score from response for item {item_id}: '{raw_response}'")

                except (ValueError, IndexError) as parse_e:
                    logger.error(f"Error parsing evaluation response for item {item_id}: {parse_e}, raw_response: {raw_response[:500]}...")
                    # Keep score as None, update reason and add error
                    reason = f"Evaluation parsing failed: {parse_e}. Raw: '{raw_response}'" # Keep full raw response in reasoning for debugging
                    eval_error = f"Evaluation parsing error: {parse_e}"

                logger.info(f"Evaluation result for item {item_id}: Score={score}, Reason='{reason}', EvalError='{eval_error}'")
                # Merge evaluation results with original item data
                return {
                    **item,
                    "score": score, # Score might be None if parsing failed
                    "scoreReasoning": reason.strip(),
                    "eval_error": eval_error, # Add the determined eval_error
                }

            except Exception as eval_e:
                # This catches errors after ChatOpenAI's internal retries (if any) are exhausted
                # Log the final error after potential retries
                logger.error(f"Evaluation Exception for item {item_id} after potential retries: {eval_e}", exc_info=True)
                # Check if the error is specifically a rate limit error (might need specific exception type from openai/langchain)
                # Example check (may need adjustment based on actual exception type):
                error_type = type(eval_e).__name__
                error_msg = f"Evaluation API Error ({error_type}): {str(eval_e)}"
                if "RateLimitError" in error_type: # Heuristic check
                    error_msg = f"Evaluation failed due to Rate Limit Error after {eval_max_retries} retries: {str(eval_e)}"

                return {
                    **item,
                    "score": None, # Indicate evaluation failed
                    "scoreReasoning": None,
                    "eval_error": error_msg,
                }

    # Create tasks for evaluation
    logger.info(f"Creating {len(results)} evaluation tasks...")
    evaluation_tasks = [_evaluate(r) for r in results]
    logger.info(f"Waiting for {len(evaluation_tasks)} evaluation tasks to complete...")
    evaluated_results = await asyncio.gather(*evaluation_tasks)
    logger.info("All evaluation tasks finished.")

    return evaluated_results
