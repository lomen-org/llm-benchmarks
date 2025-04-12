import asyncio
from ..utils.env_loader import load_env_vars, get_env
from ..core.prompt_loader import load_prompts
from ..core.executor import run_prompts
from ..core.evaluator import evaluate_responses
from ..core.aggregator import aggregate_results
from ..core.reporter import generate_html_report
from pathlib import Path
import json

def load_prompt(file_path: str) -> str:
    return Path(file_path).read_text()


# Update the prompt file path to use the correct location
prompt_file = Path(__file__).parent.parent.parent / "prompt.json"
# prompts = load_prompt(prompt_file)

with open(prompt_file) as f:
    prompts = json.load(f)

def main():
    load_env_vars()
    # prompts_file = get_env("PROMPTS_FILE", "prompts.json")
    # prompts = load_prompts(prompts_file)

    print(prompts, "#####")

    async def run():
        responses = await run_prompts(prompts)
        evaluated = await evaluate_responses(responses)
        summary = aggregate_results(evaluated)
        generate_html_report(summary, evaluated)

    asyncio.run(run())

if __name__ == "__main__":
    main()