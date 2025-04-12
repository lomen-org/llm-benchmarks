import json
import statistics
from collections import defaultdict

def aggregate_results(results):
    # Calculate overall statistics across all turns/prompts
    scored_items = [r for r in results if r.get("score") is not None]
    latencies = [r["latency"] for r in results if r.get("latency") is not None]

    overall_summary = {
        "total_items_processed": len(results), # Total turns + single prompts
        "scored_items": len(scored_items),
        "average_score_overall": round(statistics.mean(r["score"] for r in scored_items), 4) if scored_items else None,
        "average_latency_overall": round(statistics.mean(latencies), 4) if latencies else None
    }

    # Group results by conversation_id
    grouped_results = defaultdict(lambda: {"id": None, "turns": []})
    single_prompts = []

    for item in results:
        conv_id = item.get("conversation_id")
        if conv_id:
            if grouped_results[conv_id]["id"] is None:
                 grouped_results[conv_id]["id"] = conv_id
            grouped_results[conv_id]["turns"].append(item)
        else:
            # It's a single prompt result
            single_prompts.append(item)

    # Calculate per-conversation stats (optional, but useful)
    conversation_summaries = {}
    for conv_id, data in grouped_results.items():
        conv_scored = [t for t in data["turns"] if t.get("score") is not None]
        conv_latencies = [t["latency"] for t in data["turns"] if t.get("latency") is not None]
        conversation_summaries[conv_id] = {
            "total_turns": len(data["turns"]),
            "scored_turns": len(conv_scored),
            "average_score": round(statistics.mean(t["score"] for t in conv_scored), 4) if conv_scored else None,
            "total_latency": round(sum(conv_latencies), 4) if conv_latencies else None,
            "average_latency_per_turn": round(statistics.mean(conv_latencies), 4) if conv_latencies else None
        }

    # Combine grouped conversations and single prompts for the final output list
    final_structured_results = list(grouped_results.values()) + single_prompts

    # Save detailed results (grouped)
    with open("evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump(final_structured_results, f, indent=2)
    print("✅ Evaluation complete. Detailed results saved to evaluation_results.json")

    # Save summary report (overall summary + per-conversation summary)
    summary_report = {
        "overall_summary": overall_summary,
        "conversation_summaries": conversation_summaries,
        # Optionally include single prompt summaries if needed
    }
    with open("result.json", "w", encoding="utf-8") as f:
        json.dump(summary_report, f, indent=2)
    print("✅ Summary report saved to result.json")


    return overall_summary # Return the overall summary as before
