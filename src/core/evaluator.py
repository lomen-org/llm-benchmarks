import asyncio
from langchain_openai import ChatOpenAI
from ..utils.env_loader import get_env

async def evaluate_responses(results): # Renamed input from responses to results for clarity
    evaluator = ChatOpenAI(
        model_name=get_env("EVAL_MODEL", "gpt-4"),
        openai_api_key=get_env("EVAL_API_KEY", get_env("BENCHMARK_API_KEY")),
        base_url=get_env("EVAL_ENDPOINT_URL", get_env("BENCHMARK_ENDPOINT_URL"))
    )

    semaphore = asyncio.Semaphore(int(get_env("EVAL_BATCH_SIZE", 5)))

    async def _evaluate(item):
        # Extract relevant info from the result item (which represents a single turn or prompt)
        prompt_content = item.get("user_message", "") # Use user_message from the turn/prompt
        expected_answer = item.get("expected")
        actual_answer = item.get("actual")
        item_id = item.get("id") # This is now the turn_id or original prompt_id

        # Handle cases where the execution failed
        if actual_answer is None:
             return {
                "id": item_id,
                "prompt": prompt_content,
                "expected": expected_answer,
                "actual": None,
                "score": 0.0, # Assign 0 score if execution failed
                "scoreReasoning": "Execution failed, no answer generated.",
                "error": item.get("error", "Execution failed"),
                **item # Include other fields like latency, conversation_id, turn
            }

        # Build evaluation prompt dynamically
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
                "❌ Deduct points if meaning is lost, logic is incorrect, or important elements are missing.\n\n"
                "Respond with:\n"
                "1. A **single numeric score between 0 and 1**, with up to two decimal places.\n"
                "2. Followed by a short reason for this score, in **one sentence**.\n\n"
                "Format your response exactly like this:\n"
                "0.85\nReason: The actual answer matches the intent but misses some details.\n\n"
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
                "❌ Deduct points for incomplete, vague, or factually incorrect responses.\n\n"
                "Respond with:\n"
                "1. A **single numeric score between 0 and 1**, with up to two decimal places.\n"
                "2. Followed by a short reason for this score, in **one sentence**.\n\n"
                "Format your response exactly like this:\n"
                "0.90\nReason: The answer is clear, well-explained, and complete.\n\n"
                "Important: Do not add any other explanation outside this format."
            )

        eval_prompt = [
            {"role": "system", "content": "You are a strict evaluator of answers."},
            {"role": "user", "content": content}
        ]

        async with semaphore:
            try:
                res = await evaluator.ainvoke(eval_prompt)
                raw_response = res.content.strip()
                try:
                    lines = raw_response.split("\n", 1)

                    if not lines or len(lines) < 2:
                        raise ValueError(f"Unexpected response format: {raw_response}")

                    score_str, reason = lines
                    score = float(score_str.strip())
                    # Ensure score is within 0-1 range
                    score = min(1.0, max(0.0, score))
                except (ValueError, IndexError) as ve:
                    print(f"Error parsing evaluation response: {ve}, raw_response: {raw_response}")
                    # Handle parsing error - assign default score/reason or re-raise
                    score = 0.0 # Default score on parsing failure
                    reason = f"Evaluation parsing failed: {raw_response}"


                # Merge evaluation results with original item data
                return {
                    **item, # Keep original fields like latency, conversation_id, turn
                    "id": item_id, # Ensure ID is correct
                    "prompt": prompt_content, # User message for this turn/prompt
                    "expected": expected_answer,
                    "actual": actual_answer,
                    "score": score,
                    "scoreReasoning": reason.strip(),
                    "eval_error": None, # Use a different key for eval errors
                }

            except Exception as e:
                print(f"Evaluation Exception for item {item_id}: {e}")
                return {
                    **item, # Keep original fields
                    "id": item_id,
                    "prompt": prompt_content,
                    "expected": expected_answer,
                    "actual": actual_answer, # Actual might be None if execution failed earlier
                    "score": None, # Indicate evaluation failed
                    "scoreReasoning": None,
                    "eval_error": str(e), # Store evaluation-specific error
                }

    # Pass the results from the executor to the evaluator
    return await asyncio.gather(*[_evaluate(r) for r in results])
