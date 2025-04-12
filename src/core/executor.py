import asyncio
import time
import aiohttp
from ..utils.env_loader import get_env
import copy

async def run_prompts(prompts_or_conversations):
    semaphore = asyncio.Semaphore(int(get_env("BATCH_SIZE", 5)))
    base_url = get_env("BENCHMARK_ENDPOINT_URL")
    api_key = get_env("BENCHMARK_API_KEY")

    endpoint_url = f"{base_url}/api/chat/completions"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-bearer-token"] = f"{api_key}"

    results = []

    async def _run_single_turn(session, payload, turn_info):
        async with semaphore:
            start_time = time.perf_counter()
            try:
                async with session.post(endpoint_url, json=payload, headers=headers) as resp:
                    latency = time.perf_counter() - start_time
                    if resp.status != 200:
                        return {
                            **turn_info,
                            "actual": None,
                            "error": f"HTTP {resp.status}",
                            "latency": latency
                        }
                    data = await resp.json()
                    answer = data["choices"][0]["message"]["content"]
                    return {
                        **turn_info,
                        "actual": answer,
                        "latency": latency,
                        "error": None
                    }
            except Exception as e:
                return {
                    **turn_info,
                    "actual": None,
                    "error": str(e),
                    "latency": None
                }

    async with aiohttp.ClientSession() as session:
        tasks = []
        for item in prompts_or_conversations:
            if "turns" in item:  # New conversation format
                conversation_id = item["id"]
                current_messages = []
                for i, turn in enumerate(item["turns"]):
                    turn_id = f"{conversation_id}-turn-{i+1}"
                    user_message = {"role": "user", "content": turn["user"]}
                    current_messages.append(user_message)

                    payload = {
                        "messages": copy.deepcopy(current_messages), # Send history
                        "stream": False,
                        "model": "gemini-2.0-flash", # TODO: Make model configurable
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
                    results.append(result)

                    # Add assistant response to history for the next turn
                    if result.get("actual"):
                        assistant_message = {"role": "assistant", "content": result["actual"]}
                        current_messages.append(assistant_message)
                    else:
                        # If a turn failed, stop processing this conversation
                        break

            elif "messages" in item:  # Old single prompt format
                payload = {
                    "messages": item["messages"],
                    "stream": False,
                    "model": "gemini-2.0-flash", # TODO: Make model configurable
                }
                turn_info = {
                    "id": item["id"],
                    "expected": item.get("expected"),
                    "user_message": item["messages"][0]["content"] # Assuming single user message
                }
                # Schedule the task for concurrent execution
                tasks.append(_run_single_turn(session, payload, turn_info))

        # Gather results from any scheduled single-prompt tasks
        if tasks:
            single_prompt_results = await asyncio.gather(*tasks)
            results.extend(single_prompt_results)

    return results
