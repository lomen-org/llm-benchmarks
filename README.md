# LLM Benchmarker SDK

A Python SDK for benchmarking Large Language Model (LLM) responses, supporting both single prompts and multi-turn conversations, with automated evaluation using another LLM.

## Features

- Run benchmarks against any LLM API endpoint compatible with the OpenAI Chat Completions format.
- Supports both single-turn prompts and multi-turn conversations.
- Evaluates LLM responses based on semantic similarity to expected answers (if provided) or self-evaluation using a separate evaluator LLM (e.g., GPT-4).
- Calculates performance metrics like average score and latency.
- Generates detailed JSON results and summary reports.
- Produces an interactive HTML report with charts and detailed results.
- Configurable via Python dictionaries or environment variables.

## Installation

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <repository_url>
    cd llm-benchmark
    ```
2.  **Install the package and its dependencies:**
    It's recommended to use a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows use `venv\Scripts\activate`
    pip install .
    ```
    This command installs the `llm-benchmarker` package defined in `pyproject.toml` along with dependencies like `langchain-openai`, `aiohttp`, and `python-dotenv`.

## Usage

Import the `run_benchmark` function and call it with a configuration dictionary.

```python
import asyncio
import json
import os
from llm_benchmarker import run_benchmark

async def main():
    # --- Configuration ---

    # Set necessary API keys and endpoints either here or as environment variables
    # os.environ["BENCHMARK_API_KEY"] = "YOUR_API_KEY"
    # os.environ["BENCHMARK_ENDPOINT_URL"] = "YOUR_API_ENDPOINT"
    # os.environ["EVAL_API_KEY"] = "YOUR_EVAL_KEY" # Can fallback to BENCHMARK_API_KEY
    # os.environ["EVAL_ENDPOINT_URL"] = "YOUR_EVAL_ENDPOINT" # Can fallback to BENCHMARK_ENDPOINT_URL

    config = {
        # --- Input ---
        # Option 1: Load prompts from a JSON file
        "prompt_file_path": "prompt.json",

        # Option 2: Provide prompts directly as a list
        # "prompts_data": [
        #     {
        #         "id": "conv-001",
        #         "turns": [
        #             {"user": "What is AI?", "expected": "Artificial Intelligence is..."},
        #             {"user": "Give an example.", "expected": "An example is..."}
        #         ]
        #     },
        #     {
        #         "id": "single-001",
        #         "messages": [{"role": "user", "content": "Explain quantum computing."}]
        #     }
        # ],

        # --- Output ---
        "output_dir": "benchmark_output", # Directory to save results (default: '.')
        "save_results": True,             # Save detailed results JSON (default: True)
        "results_filename": "evaluation_results.json", # (default)
        "save_summary": True,             # Save summary JSON (default: True)
        "summary_filename": "result.json", # (default)
        "save_report": True,              # Save HTML report (default: True)
        "report_filename": "report.html",  # (default)

        # --- Execution Configuration (Optional - overrides env vars) ---
        "executor_config": {
            "endpoint_url": os.getenv("BENCHMARK_ENDPOINT_URL"), # Example: Load from env
            "api_key": os.getenv("BENCHMARK_API_KEY"),
            "model": "your-target-model-name", # Specify the model to benchmark
            "batch_size": 5                  # Max concurrent requests to benchmark endpoint
            # "headers": {"X-Custom-Header": "value"} # Optional additional headers
        },

        # --- Evaluation Configuration (Optional - overrides env vars) ---
        "evaluator_config": {
            "eval_model": "gpt-4",           # Model used for evaluation
            "eval_api_key": os.getenv("EVAL_API_KEY", os.getenv("BENCHMARK_API_KEY")), # API key for evaluator
            "eval_endpoint_url": os.getenv("EVAL_ENDPOINT_URL", os.getenv("BENCHMARK_ENDPOINT_URL")), # Endpoint for evaluator
            "eval_batch_size": 3             # Max concurrent requests to evaluator endpoint
        }
        # reporter_config is currently unused but available for future extensions
    }

    # --- Run Benchmark ---
    print("Running benchmark...")
    results_data = await run_benchmark(config)
    print("Benchmark finished.")

    # --- Process Results (Optional) ---
    if "summary_report" in results_data:
        print("\n--- Benchmark Summary ---")
        print(json.dumps(results_data["summary_report"], indent=2))

        # You can also access detailed results:
        # structured_results = results_data["structured_results"]
        # print(f"\nProcessed {len(structured_results)} conversations/prompts.")

    elif "error" in results_data:
         print(f"\n--- Benchmark Error ---")
         print(results_data["error"])


if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration Details

The `run_benchmark` function takes a single `config` dictionary. Key options:

- **Input Data:**
  - `prompt_file_path` (str): Path to a JSON file containing a list of prompts/conversations (see format below).
  - `prompts_data` (list): A list of prompt/conversation dictionaries provided directly.
  - _Note:_ You must provide _either_ `prompt_file_path` _or_ `prompts_data\*.
- **Output Control:**
  - `output_dir` (str): Directory where result files (`.json`, `.html`) will be saved. Defaults to the current directory (`.`).
  - `save_results`, `save_summary`, `save_report` (bool): Flags to control whether the detailed results, summary JSON, and HTML report are saved. Default to `True`.
  - `results_filename`, `summary_filename`, `report_filename` (str): Customize the names of the output files.
- **Executor Config (`executor_config` dict):** Controls the execution against the benchmarked LLM.
  - `endpoint_url` (str): **Required** (either here or via `BENCHMARK_ENDPOINT_URL` env var). The API endpoint URL.
  - `api_key` (str): API key (either here or via `BENCHMARK_API_KEY` env var).
  - `model` (str): **Required**. The name of the LLM model to benchmark.
  - `batch_size` (int): Maximum number of concurrent API requests. Defaults to `5` or `BATCH_SIZE` env var.
  - `headers` (dict): Optional dictionary of additional HTTP headers to send.
- **Evaluator Config (`evaluator_config` dict):** Controls the evaluation LLM.
  - `eval_model` (str): The name of the model used for evaluation (e.g., `gpt-4`). Defaults to `gpt-4` or `EVAL_MODEL` env var.
  - `eval_api_key` (str): API key for the evaluator. Defaults to `EVAL_API_KEY` env var, falling back to `BENCHMARK_API_KEY`.
  - `eval_endpoint_url` (str): Endpoint for the evaluator. Defaults to `EVAL_ENDPOINT_URL` env var, falling back to `BENCHMARK_ENDPOINT_URL`. Can be omitted if using default OpenAI endpoint.
  - `eval_batch_size` (int): Maximum number of concurrent evaluation requests. Defaults to `5` or `EVAL_BATCH_SIZE` env var.

### Environment Variable Fallback

If configuration values (like API keys, endpoints, batch sizes) are _not_ provided directly within the `executor_config` or `evaluator_config` dictionaries, the SDK will attempt to load them from the following environment variables:

- `BENCHMARK_ENDPOINT_URL`, `BENCHMARK_API_KEY`, `BENCHMARK_MODEL`, `BATCH_SIZE`
- `EVAL_MODEL`, `EVAL_API_KEY`, `EVAL_ENDPOINT_URL`, `EVAL_BATCH_SIZE`

This allows you to configure sensitive keys or common settings outside your script using tools like `.env` files (loaded via `python-dotenv`, which is included as a dependency).

## Prompt File Format (`prompt.json`)

The JSON file specified by `prompt_file_path` should contain a list of dictionaries. Each dictionary represents either a single prompt or a multi-turn conversation:

**1. Single Prompt:**

```json
[
  {
    "id": "unique-prompt-id-001",
    "messages": [
      { "role": "user", "content": "What is the capital of France?" }
    ],
    "expected": "The capital of France is Paris." // Optional: Reference answer for evaluation
  }
]
```

**2. Multi-Turn Conversation:**

```json
[
  {
    "id": "unique-conversation-id-001",
    "turns": [
      {
        "user": "What is the current price of bitcoin in USD?", // User's message for turn 1
        "expected": "The current price of Bitcoin is approximately $X USD." // Optional: Expected answer for turn 1
      },
      {
        "user": "How volatile has it been in the last 24 hours?", // User's message for turn 2
        "expected": "Bitcoin has shown [low/medium/high] volatility..." // Optional: Expected answer for turn 2
      }
      // Add more turns as needed
    ]
  }
]
```

- **`id`**: A unique identifier for the prompt or conversation.
- **`messages`**: (For single prompts) A list containing message objects (typically one user message).
- **`turns`**: (For conversations) A list of turn objects. Each turn object must have a `user` key with the user's message content. It can optionally have an `expected` key for the reference answer for that specific turn.
- **`expected`**: (Optional) The reference answer used by the evaluator LLM. If omitted, the evaluator performs self-evaluation based on clarity, correctness, and completeness.

## Output Files

If enabled via configuration, the benchmark run will produce:

1.  **`evaluation_results.json`** (or custom name): A detailed JSON file containing a list of results.
    - For conversations, each item is an object with the `id` and a `turns` list containing the detailed result (prompt, actual, expected, score, latency, errors, etc.) for each turn.
    - For single prompts, each item is the detailed result dictionary for that prompt.
2.  **`result.json`** (or custom name): A summary JSON file containing:
    - `overall_summary`: Statistics aggregated across all processed turns and single prompts (average score, average latency, error counts, etc.).
    - `conversation_summaries`: Statistics aggregated for each individual conversation ID.
3.  **`report.html`** (or custom name): An interactive HTML report visualizing the results with charts and a detailed table of all turns/prompts.

## Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request. (TODO: Add contribution guidelines if desired).

## License

(TODO: Specify the license chosen in `pyproject.toml`, e.g., MIT License).
