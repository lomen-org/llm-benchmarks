import html
import json
from itertools import chain

def generate_html_report(summary_report, structured_results):
    # Flatten the structured results (conversations + single prompts) into a list of individual items (turns/prompts)
    flat_results = []
    for item in structured_results:
        if "turns" in item: # It's a conversation object
            flat_results.extend(item["turns"])
        else: # It's a single prompt object
            flat_results.append(item)

    # Extract data for charts and table from the flattened list
    labels = [html.escape(res.get("id", "N/A")) for res in flat_results]
    # Use score 0 if None for charting, but display 'N/A' in table
    score_values = [res.get("score", 0) if res.get("score") is not None else 0 for res in flat_results]
    latency_values = [res.get("latency", 0) if res.get("latency") is not None else 0 for res in flat_results]

    # Access the overall summary correctly
    overall_summary = summary_report.get("overall_summary", {})
    avg_score = overall_summary.get("average_score_overall")
    avg_latency = overall_summary.get("average_latency_overall")
    total_items = overall_summary.get("total_items_processed", len(flat_results))
    scored_items = overall_summary.get("scored_items", len([s for s in score_values if s is not None]))


    html_content = [
        "<html><head><title>LLM Benchmark Report</title>",
        "<script src='https://cdn.jsdelivr.net/npm/chart.js'></script>",
        "<style>body { font-family: Arial, sans-serif; margin: 20px; } table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid #ddd; padding: 8px; text-align: left; } th { background-color: #f2f2f2; } .conv-turn { padding-left: 20px; font-style: italic; color: #555; }</style>",
        "</head><body>",
        "<h1>LLM Benchmark Report</h1>",
        # Updated Summary Section
        f"<h2>Overall Summary</h2><p>Total Items Processed (Turns + Single Prompts): {total_items}<br>",
        f"Scored Items: {scored_items}<br>",
        f"Average Score (Overall): {avg_score:.4f}" if avg_score is not None else "N/A", "<br>",
        f"Average Latency (Overall): {avg_latency:.4f} sec" if avg_latency is not None else "N/A", "</p>",

        # TODO: Optionally add per-conversation summary table here if needed

        "<h2>Charts (Based on Individual Turns/Prompts)</h2>",
        "<canvas id='scoreChart' width='800' height='400'></canvas>",
        "<canvas id='latencyChart' width='800' height='400'></canvas>",
        "<script>",
        # Use flattened data for charts
        f"const labels = {json.dumps(labels)};\nconst scores = {json.dumps(score_values)};\nconst latencies = {json.dumps(latency_values)};",
        "const ctx = document.getElementById('scoreChart').getContext('2d');",
        "new Chart(ctx, { type: 'bar', data: { labels, datasets: [{ label: 'Score', data: scores }] }, options: { scales: { y: { beginAtZero: true, max: 1 } } } });",
        "const ctx2 = document.getElementById('latencyChart').getContext('2d');",
        "new Chart(ctx2, { type: 'bar', data: { labels, datasets: [{ label: 'Latency (s)', data: latencies }] }, options: { scales: { y: { beginAtZero: true } } } });",
        "</script>",
        "<h2>Detailed Results (Turns and Single Prompts)</h2>",
        "<table><tr><th>ID (Turn/Prompt)</th><th>Prompt/User Message</th><th>Expected</th><th>Actual</th><th>Score</th><th>Reasoning</th><th>Latency (s)</th><th>Error</th></tr>",
    ]

    # Iterate through the flattened results for the details table
    for res in flat_results:
        # Display 'N/A' for None values in the table
        score_display = f"{res.get('score'):.2f}" if res.get('score') is not None else "N/A"
        latency_display = f"{res.get('latency'):.4f}" if res.get('latency') is not None else "N/A"
        error_display = html.escape(res.get('error') or res.get('eval_error') or '')

        # Add class if it's part of a conversation for potential styling
        row_class = " class='conv-turn'" if "conversation_id" in res else ""

        row = f"<tr{row_class}>"
        row += f"<td>{html.escape(res.get('id', 'N/A'))}</td>"
        row += f"<td>{html.escape(res.get('prompt', '') or res.get('user_message', ''))}</td>" # Show prompt/user message
        row += f"<td>{html.escape(res.get('expected', '') or '')}</td>"
        row += f"<td>{html.escape(res.get('actual', '') or '')}</td>" # Show actual response
        row += f"<td>{score_display}</td>"
        row += f"<td>{html.escape(res.get('scoreReasoning', '') or '')}</td>" # Show reasoning
        row += f"<td>{latency_display}</td>"
        row += f"<td>{error_display}</td>" # Show errors
        row += "</tr>"
        html_content.append(row)

    html_content.append("</table></body></html>")

    report = "".join(html_content)
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(report)
