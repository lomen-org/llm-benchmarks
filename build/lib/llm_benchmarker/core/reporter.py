import html
import json
from typing import List, Dict, Any, Optional

def generate_html_report(
    summary_report: Dict[str, Any],
    structured_results: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None # Keep config for consistency, though not used yet
) -> str:
    """
    Generates an HTML report string from the benchmark summary and results.

    Args:
        summary_report: The summary report dictionary from the aggregator.
        structured_results: The list of structured results (grouped conversations
                            and single prompts) from the aggregator.
        config: Optional configuration dictionary (currently unused).

    Returns:
        A string containing the HTML report.
    """
    # Flatten the structured results for charts and detailed table
    flat_results = []
    for item in structured_results:
        if "turns" in item and isinstance(item.get("turns"), list): # It's a conversation object
            flat_results.extend(item["turns"])
        elif isinstance(item, dict): # It's a single prompt object or potentially malformed item
             # Check if it looks like a result item before appending
             if "id" in item:
                flat_results.append(item)
             else:
                 print(f"Warning: Skipping malformed item in structured_results: {item}")
        else:
             print(f"Warning: Skipping unexpected data type in structured_results: {type(item)}")


    # --- Data Extraction for Report ---
    labels = []
    score_values = []
    latency_values = []

    for res in flat_results:
         # Ensure res is a dictionary before accessing keys
         if not isinstance(res, dict):
             print(f"Warning: Skipping non-dictionary item in flat_results: {res}")
             continue

         labels.append(html.escape(res.get("id", "N/A")))
         # Use score 0 if None for charting, handle potential non-numeric scores gracefully
         try:
             score = res.get("score")
             score_values.append(float(score) if score is not None else 0.0)
         except (ValueError, TypeError):
             score_values.append(0.0) # Default to 0 if score is not a valid number

         # Use latency 0 if None for charting, handle potential non-numeric latencies
         try:
             latency = res.get("latency")
             latency_values.append(float(latency) if latency is not None else 0.0)
         except (ValueError, TypeError):
             latency_values.append(0.0) # Default to 0 if latency is not valid


    # Access the overall summary safely
    overall_summary = summary_report.get("overall_summary", {})
    avg_score = overall_summary.get("average_score_overall")
    avg_latency = overall_summary.get("average_latency_overall")
    total_items = overall_summary.get("total_items_processed", len(flat_results)) # Fallback if summary missing
    scored_items_count = overall_summary.get("scored_items", len([s for s in score_values if s is not None])) # Fallback


    # --- HTML Generation ---
    html_content = [
        "<!DOCTYPE html>",
        "<html lang='en'><head>",
        "<meta charset='UTF-8'>",
        "<title>LLM Benchmark Report</title>",
        "<script src='https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js'></script>", # Use specific version
        "<style>",
        "body { font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; margin: 20px; background-color: #f9f9f9; color: #333; }",
        "h1, h2 { color: #1a1a1a; border-bottom: 1px solid #eee; padding-bottom: 5px; }",
        "table { border-collapse: collapse; width: 100%; margin-bottom: 20px; background-color: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }",
        "th, td { border: 1px solid #ddd; padding: 10px; text-align: left; vertical-align: top; }",
        "th { background-color: #f2f2f2; font-weight: bold; }",
        "tr:nth-child(even) { background-color: #f9f9f9; }",
        ".summary-box { background-color: #fff; padding: 15px; margin-bottom: 20px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }",
        ".chart-container { background-color: #fff; padding: 15px; margin-bottom: 20px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }",
        ".conv-turn td:first-child { padding-left: 30px; }", # Indent turn IDs
        ".error { color: #d9534f; font-weight: bold; }",
        "pre { background-color: #eee; padding: 10px; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; font-family: monospace; }",
        "</style>",
        "</head><body>",
        "<h1>LLM Benchmark Report</h1>",

        # --- Overall Summary Section ---
        "<div class='summary-box'>",
        "<h2>Overall Summary</h2>",
        f"<p>Total Items Processed (Turns + Single Prompts): <strong>{total_items}</strong><br>",
        f"Successfully Completed Items: <strong>{overall_summary.get('successfully_completed_items', 'N/A')}</strong><br>",
        f"Scored Items: <strong>{scored_items_count}</strong><br>",
        f"Items with Errors: <strong class='error'>{overall_summary.get('error_items', 'N/A')}</strong><br>",
        f"Average Score (Overall): <strong>{avg_score:.4f}</strong>" if avg_score is not None else "N/A", "<br>",
        f"Average Latency (Overall): <strong>{avg_latency:.4f} sec</strong>" if avg_latency is not None else "N/A", "<br>",
        f"Median Latency (Overall): <strong>{overall_summary.get('median_latency_overall', 'N/A'):.4f} sec</strong>" if overall_summary.get('median_latency_overall') is not None else "N/A", "<br>",
        f"Latency Range (min-max): <strong>{overall_summary.get('min_latency_overall', 'N/A'):.4f} - {overall_summary.get('max_latency_overall', 'N/A'):.4f} sec</strong>" if overall_summary.get('min_latency_overall') is not None else "N/A",
        "</p></div>",

        # --- Per-Conversation Summary (Optional Table) ---
        # You could add a table summarizing conversation_summaries here if desired

        # --- Charts Section ---
        "<div class='chart-container'>",
        "<h2>Charts (Based on Individual Turns/Prompts)</h2>",
        "<canvas id='scoreChart' style='max-width: 100%;'></canvas>", # Responsive width
        "<canvas id='latencyChart' style='max-width: 100%; margin-top: 20px;'></canvas>", # Add margin
        "</div>", # Close chart-container
        "<script>",
        f"const benchmarkLabels = {json.dumps(labels)};",
        f"const benchmarkScores = {json.dumps(score_values)};",
        f"const benchmarkLatencies = {json.dumps(latency_values)};",
        # Score Chart
        "const scoreCtx = document.getElementById('scoreChart').getContext('2d');",
        "new Chart(scoreCtx, {",
        "  type: 'bar',",
        "  data: { labels: benchmarkLabels, datasets: [{ label: 'Score', data: benchmarkScores, backgroundColor: 'rgba(75, 192, 192, 0.6)', borderColor: 'rgba(75, 192, 192, 1)', borderWidth: 1 }] },",
        "  options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, max: 1, title: { display: true, text: 'Score' } } } }",
        "});",
        # Latency Chart
        "const latencyCtx = document.getElementById('latencyChart').getContext('2d');",
        "new Chart(latencyCtx, {",
        "  type: 'bar',",
        "  data: { labels: benchmarkLabels, datasets: [{ label: 'Latency (s)', data: benchmarkLatencies, backgroundColor: 'rgba(255, 159, 64, 0.6)', borderColor: 'rgba(255, 159, 64, 1)', borderWidth: 1 }] },",
        "  options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, title: { display: true, text: 'Latency (s)' } } } }",
        "});",
        "</script>",

        # --- Detailed Results Table ---
        "<h2>Detailed Results (Turns and Single Prompts)</h2>",
        "<table><thead><tr>",
        "<th>ID (Turn/Prompt)</th><th>Prompt/User Message</th><th>Expected</th><th>Actual</th><th>Score</th><th>Reasoning</th><th>Latency (s)</th><th>Error</th>",
        "</tr></thead><tbody>",
    ]

    # Iterate through the flattened results for the details table
    for res in flat_results:
         # Ensure res is a dictionary
         if not isinstance(res, dict): continue

         # Display 'N/A' or format values
         score_val = res.get('score')
         score_display = f"{score_val:.2f}" if score_val is not None else "N/A"
         latency_val = res.get('latency')
         latency_display = f"{latency_val:.4f}" if latency_val is not None else "N/A"
         error_msg = res.get('error') or res.get('eval_error') or ''
         error_display = f"<span class='error'>{html.escape(error_msg)}</span>" if error_msg else ""

         # Add class if it's part of a conversation
         row_class = " class='conv-turn'" if "conversation_id" in res else ""

         row = f"<tr{row_class}>"
         row += f"<td>{html.escape(res.get('id', 'N/A'))}</td>"
         # Use <pre> for potentially long messages
         row += f"<td><pre>{html.escape(res.get('prompt', '') or res.get('user_message', ''))}</pre></td>"
         row += f"<td><pre>{html.escape(res.get('expected', '') or '')}</pre></td>"
         row += f"<td><pre>{html.escape(res.get('actual', '') or '')}</pre></td>"
         row += f"<td>{score_display}</td>"
         row += f"<td>{html.escape(res.get('scoreReasoning', '') or '')}</td>"
         row += f"<td>{latency_display}</td>"
         row += f"<td>{error_display}</td>"
         row += "</tr>"
         html_content.append(row)

    html_content.append("</tbody></table></body></html>") # Close table body and html

    # Join and return the HTML string
    report_html = "".join(html_content)
    return report_html

# Note: File writing is removed. The caller function will handle saving the report.
