import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime # Import datetime

from .core import prompt_loader, executor, evaluator, aggregator, reporter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def run_benchmark(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs the LLM benchmark process based on the provided configuration.

    Args:
        config: A dictionary containing the benchmark configuration.
                Expected keys include:
                - prompt_file_path OR prompts_data: Source of prompts.
                - output_dir (str, optional): Directory to save results. Defaults to current dir.
                - save_results (bool, optional): Whether to save detailed results JSON. Defaults to True.
                - results_filename (str, optional): Filename for detailed results. Defaults to 'evaluation_results.json'.
                - save_summary (bool, optional): Whether to save summary JSON. Defaults to True.
                - summary_filename (str, optional): Filename for summary. Defaults to 'result.json'.
                - save_report (bool, optional): Whether to save HTML report. Defaults to True.
                - report_filename (str, optional): Filename for HTML report. Defaults to 'report.html'.
                - executor_config (dict, optional): Config passed to executor.run_prompts.
                - evaluator_config (dict, optional): Config passed to evaluator.evaluate_responses.
                - reporter_config (dict, optional): Config passed to reporter.generate_html_report.

    Returns:
        A dictionary containing the summary_report and structured_results.
    """
    logging.info("Starting LLM benchmark run...")
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") # Generate timestamp

    # --- Configuration Defaults & Filename Generation ---
    output_dir = config.get("output_dir", ".")
    save_results = config.get("save_results", True)
    # Use provided filename or generate timestamped default with "result_" prefix
    results_filename = config.get("results_filename", f"result_{run_timestamp}.json")
    save_summary = config.get("save_summary", True)
    summary_filename = config.get("summary_filename", f"summary_{run_timestamp}.json")
    save_report = config.get("save_report", True)
    report_filename = config.get("report_filename", f"report_{run_timestamp}.html")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    logging.info(f"Output directory: {os.path.abspath(output_dir)}")

    # --- Load Prompts ---
    try:
        logging.info("Loading prompts...")
        # Pass the main config to loader, it will extract relevant keys
        prompts = prompt_loader.load_prompts(config)
        if not prompts:
            logging.error("No valid prompts loaded. Aborting benchmark.")
            return {"error": "No valid prompts loaded."}
    except (ValueError, FileNotFoundError, IOError, json.JSONDecodeError) as e:
        logging.error(f"Failed to load prompts: {e}")
        return {"error": f"Failed to load prompts: {e}"}

    # --- Execute Prompts ---
    try:
        logging.info(f"Executing {len(prompts)} prompts/conversations...")
        executor_config = config.get("executor_config", {})
        execution_results = await executor.run_prompts(prompts, config=executor_config)
        logging.info("Execution finished.")
    except Exception as e:
        logging.error(f"An error occurred during prompt execution: {e}", exc_info=True)
        return {"error": f"Execution failed: {e}"}

    # --- Evaluate Responses ---
    try:
        logging.info("Evaluating responses...")
        evaluator_config = config.get("evaluator_config", {})
        evaluated_results = await evaluator.evaluate_responses(execution_results, config=evaluator_config)
        logging.info("Evaluation finished.")
    except Exception as e:
        logging.error(f"An error occurred during evaluation: {e}", exc_info=True)
        # Proceed with aggregation even if evaluation fails, using potentially partial results
        evaluated_results = execution_results # Use execution results if eval failed mid-way
        logging.warning("Proceeding with aggregation using execution results due to evaluation error.")


    # --- Aggregate Results ---
    try:
        logging.info("Aggregating results...")
        # Aggregator doesn't strictly need config currently, but pass for consistency
        summary_report, structured_results = aggregator.aggregate_results(evaluated_results)
        logging.info("Aggregation finished.")
    except Exception as e:
        logging.error(f"An error occurred during aggregation: {e}", exc_info=True)
        return {"error": f"Aggregation failed: {e}", "partial_results": evaluated_results}

    # --- Save Outputs ---
    results_path = os.path.join(output_dir, results_filename)
    summary_path = os.path.join(output_dir, summary_filename)
    report_path = os.path.join(output_dir, report_filename)

    if save_results:
        try:
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(structured_results, f, indent=2, ensure_ascii=False)
            logging.info(f"Detailed results saved to: {results_path}")
        except Exception as e:
            logging.error(f"Failed to save detailed results: {e}")

    if save_summary:
        try:
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary_report, f, indent=2, ensure_ascii=False)
            logging.info(f"Summary report saved to: {summary_path}")
        except Exception as e:
            logging.error(f"Failed to save summary report: {e}")

    # --- Generate and Save HTML Report ---
    if save_report:
        try:
            logging.info("Generating HTML report...")
            reporter_config = config.get("reporter_config", {})
            report_html = reporter.generate_html_report(summary_report, structured_results, config=reporter_config)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_html)
            logging.info(f"HTML report saved to: {report_path}")
        except Exception as e:
            logging.error(f"Failed to generate or save HTML report: {e}", exc_info=True)

    logging.info("LLM benchmark run finished.")

    # Return the aggregated results
    return {
        "summary_report": summary_report,
        "structured_results": structured_results
    }

# Example usage (can be placed in a separate script or __main__ block)
# async def main():
#     config = {
#         "prompt_file_path": "prompt.json", # Or use "prompts_data": [...]
#         "output_dir": "benchmark_results",
#         "save_results": True,
#         "save_summary": True,
#         "save_report": True,
#         "executor_config": {
#             # "endpoint_url": "YOUR_API_ENDPOINT", # Loaded from env if not set
#             # "api_key": "YOUR_API_KEY",         # Loaded from env if not set
#             # "model": "specific-model-name",
#             "batch_size": 10
#         },
#         "evaluator_config": {
#             # "eval_model": "gpt-4-turbo",
#             # "eval_api_key": "YOUR_EVAL_KEY",
#             # "eval_endpoint_url": "YOUR_EVAL_ENDPOINT",
#             "eval_batch_size": 5
#         }
#     }
#     results = await run_benchmark(config)
#     # print(json.dumps(results["summary_report"], indent=2))

# if __name__ == "__main__":
#     asyncio.run(main())
