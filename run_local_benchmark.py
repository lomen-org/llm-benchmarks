# Save this code as e.g., run_local_benchmark.py in the project root

import asyncio
import json
import os
import sys

# --- IMPORTANT: Add the project root to Python path ---
# This allows importing 'llm_benchmarker' directly when running the script
# from the project root directory, without needing to install it.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# -----------------------------------------------------

from llm_benchmarker import run_benchmark

# --- IMPORTANT ---
# Before running, ensure you have:
# 1. Installed dependencies: `pip install .` (or `pip install aiohttp langchain-openai python-dotenv`)
#    in your virtual environment.
# 2. Set necessary API keys/endpoints:
#    - Either directly in the `config` dictionary below.
#    - Or as environment variables (e.g., BENCHMARK_API_KEY, EVAL_API_KEY).
#      This script will now explicitly load a `.env` file if it exists in the project root.

async def main():
    # --- Configuration ---
    config = {
        # --- Input ---
        # Ensure prompt.json exists in the project root, or change the path
        "prompt_file_path": "prompt.json",

        # --- Output ---
        "output_dir": "lomen_benchmark_output", # Directory to save results
        "save_results": True,
        "results_filename": "detailed_results.json",
        "save_summary": True,
        "summary_filename": "summary.json",
        "save_report": True,
        "report_filename": "benchmark_report.html",

        # --- Execution Configuration (Benchmark Target LLM) ---
        "executor_config": {
            # **REQUIRED**: Set Endpoint URL either here or via BENCHMARK_ENDPOINT_URL env var
            "endpoint_url": f"{os.getenv("BENCHMARK_ENDPOINT_URL", "")}/api/chat/completions",
            # **REQUIRED**: Set API Key either here or via BENCHMARK_API_KEY env var
            "api_key": os.getenv("BENCHMARK_API_KEY", ""),
            # **REQUIRED**: Specify the model name you want to benchmark
            "model": os.getenv("BENCHMARK_MODEL", "gpt-4"),
            # Optional: Adjust batch size
            "batch_size": int(os.getenv("BATCH_SIZE", 5)),
        },

        # --- Evaluation Configuration (Evaluator LLM) ---
        "evaluator_config": {
            "eval_model": os.getenv("EVAL_MODEL", "gpt-4"),
            "eval_api_key": os.getenv("EVAL_API_KEY", os.getenv("BENCHMARK_API_KEY", "YOUR_EVAL_API_KEY_HERE")),
            "eval_endpoint_url": os.getenv("EVAL_ENDPOINT_URL", os.getenv("BENCHMARK_ENDPOINT_URL")),
            "eval_batch_size": int(os.getenv("EVAL_BATCH_SIZE", 3))
        }
    }
    # --- Run Benchmark ---
    print(f"Starting local benchmark run. Results will be saved in '{config.get('output_dir', 'local_benchmark_output')}'...")
    results_data = await run_benchmark(config)
    print("Benchmark run finished.")

    # --- Process Results (Optional) ---
    if "summary_report" in results_data:
        print("\n--- Benchmark Summary ---")
        print(json.dumps(results_data["summary_report"], indent=2))
    elif "error" in results_data:
         print(f"\n--- Benchmark Error ---")
         print(f"An error occurred: {results_data['error']}")

    print(f"\nCheck the '{config.get('output_dir', 'local_benchmark_output')}' directory for results.")


if __name__ == "__main__":
    # Make sure to configure API keys/endpoints in the config dict above
    # or set them as environment variables before running this script.
    asyncio.run(main())
