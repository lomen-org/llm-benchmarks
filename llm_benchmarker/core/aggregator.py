import statistics
from collections import defaultdict
from typing import List, Dict, Any, Tuple

def aggregate_results(results: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Aggregates evaluation results, calculates summaries, and groups by conversation.

    Args:
        results: A list of evaluated result dictionaries (from evaluator).

    Returns:
        A tuple containing:
        - summary_report (dict): Contains overall and per-conversation summaries.
        - final_structured_results (list): Results grouped by conversation,
          with single prompts as individual items.
    """
    # Calculate overall statistics across all turns/prompts
    scored_items = [r for r in results if r.get("score") is not None and r.get("error") is None and r.get("eval_error") is None] # Only count successfully scored items
    # Calculate latency only for items that have a latency value
    latencies = [r["latency"] for r in results if r.get("latency") is not None]
    # Count items with any error (execution or evaluation)
    error_items = [r for r in results if r.get("error") or r.get("eval_error")]

    overall_summary = {
        "total_items_processed": len(results), # Total turns + single prompts processed
        "successfully_completed_items": len(results) - len(error_items), # Items without execution or eval error
        "scored_items": len(scored_items), # Items successfully scored by evaluator
        "error_items": len(error_items), # Items with execution or eval error
        "average_score_overall": round(statistics.mean(r["score"] for r in scored_items), 4) if scored_items else None,
        "average_latency_overall": round(statistics.mean(latencies), 4) if latencies else None,
        "median_latency_overall": round(statistics.median(latencies), 4) if latencies else None,
        "min_latency_overall": round(min(latencies), 4) if latencies else None,
        "max_latency_overall": round(max(latencies), 4) if latencies else None,
    }

    # Group results by conversation_id
    grouped_results = defaultdict(lambda: {"id": None, "turns": [], "conversation_summary": {}})
    single_prompts = [] # Store single prompts separately initially

    for item in results:
        conv_id = item.get("conversation_id")
        if conv_id:
            # Ensure the conversation ID is set
            if grouped_results[conv_id]["id"] is None:
                grouped_results[conv_id]["id"] = conv_id
            # Add the turn to the conversation
            grouped_results[conv_id]["turns"].append(item)
        else:
            # It's a single prompt result
            single_prompts.append(item)

    # Calculate per-conversation stats and add them to the grouped_results dict
    for conv_id, data in grouped_results.items():
        conv_turns = data["turns"]
        conv_scored = [t for t in conv_turns if t.get("score") is not None and t.get("error") is None and t.get("eval_error") is None]
        conv_latencies = [t["latency"] for t in conv_turns if t.get("latency") is not None]
        conv_errors = [t for t in conv_turns if t.get("error") or t.get("eval_error")]

        data["conversation_summary"] = {
            "total_turns": len(conv_turns),
            "successfully_completed_turns": len(conv_turns) - len(conv_errors),
            "scored_turns": len(conv_scored),
            "error_turns": len(conv_errors),
            "average_score": round(statistics.mean(t["score"] for t in conv_scored), 4) if conv_scored else None,
            "total_latency": round(sum(conv_latencies), 4) if conv_latencies else None,
            "average_latency_per_turn": round(statistics.mean(conv_latencies), 4) if conv_latencies else None,
            "median_latency_per_turn": round(statistics.median(conv_latencies), 4) if conv_latencies else None,
            "min_latency_per_turn": round(min(conv_latencies), 4) if conv_latencies else None,
            "max_latency_per_turn": round(max(conv_latencies), 4) if conv_latencies else None,
        }

    # Combine grouped conversations and single prompts for the final structured results list
    # We extract the conversation summaries for the summary report before combining
    conversation_summaries = {conv_id: data["conversation_summary"] for conv_id, data in grouped_results.items()}
    final_structured_results = list(grouped_results.values()) + single_prompts

    # Prepare the summary report dictionary
    summary_report = {
        "overall_summary": overall_summary,
        "conversation_summaries": conversation_summaries,
        # We could add summaries for single prompts here if needed
    }

    # Return the summary report and the structured results
    # File writing is now handled by the caller (e.g., the main SDK runner)
    return summary_report, final_structured_results
