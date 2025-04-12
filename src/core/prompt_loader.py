import json
import os
import logging

logging.basicConfig(level=logging.INFO)

def load_prompts(file_path: str):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logging.error("Failed to load prompts file: %s", e)
        raise

    prompts = []
    for entry in data:
        prompt_id = entry.get("id")
        messages = entry.get("messages", [])
        expected = entry.get("expected", None)
        prompts.append({
            "id": prompt_id,
            "messages": messages,
            "expected": expected
        })
    logging.info("Loaded %d prompts from %s", len(prompts), file_path)
    return prompts