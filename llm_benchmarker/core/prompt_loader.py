import json
import logging
from typing import List, Dict, Any, Optional, Union

logging.basicConfig(level=logging.INFO)

def load_prompts(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Loads prompts either from a specified file path or directly from configuration data.

    Args:
        config: An optional dictionary containing configuration like:
            prompt_file_path (str): Path to the JSON file containing prompts.
            prompts_data (list): A list of prompt/conversation dictionaries.
            One of these must be provided.

    Returns:
        A list of prompt/conversation dictionaries.

    Raises:
        ValueError: If neither prompt_file_path nor prompts_data is provided,
                    or if the data format is invalid.
        FileNotFoundError: If prompt_file_path is provided but the file doesn't exist.
        IOError: If there's an error reading the prompt file.
        json.JSONDecodeError: If the prompt file contains invalid JSON.
    """
    cfg = config or {}
    prompt_file_path = cfg.get("prompt_file_path")
    prompts_data = cfg.get("prompts_data")

    if prompts_data is not None:
        logging.info("Loading prompts directly from configuration data.")
        if not isinstance(prompts_data, list):
            raise ValueError("Invalid format: 'prompts_data' must be a list.")
        data = prompts_data # Use the provided list directly
    elif prompt_file_path:
        logging.info(f"Loading prompts from file: {prompt_file_path}")
        try:
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                 raise ValueError(f"Invalid format: JSON file '{prompt_file_path}' must contain a list.")
        except FileNotFoundError:
            logging.error(f"Prompt file not found: {prompt_file_path}")
            raise
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON from {prompt_file_path}: {e}")
            raise ValueError(f"Invalid JSON in {prompt_file_path}") from e
        except Exception as e:
            logging.error(f"Failed to load prompts file {prompt_file_path}: {e}")
            raise IOError(f"Error reading prompt file {prompt_file_path}") from e
    else:
        raise ValueError("Configuration must provide either 'prompt_file_path' or 'prompts_data'.")

    # Basic validation of loaded/provided data structure
    validated_prompts = []
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            logging.warning(f"Skipping invalid entry at index {i}: Expected a dictionary, got {type(entry)}")
            continue

        prompt_id = entry.get("id")
        if not prompt_id:
            logging.warning(f"Skipping entry at index {i}: Missing required 'id' field.")
            continue

        # Check for either 'messages' (old format) or 'turns' (new format)
        if "messages" in entry and isinstance(entry["messages"], list):
             validated_prompts.append({
                "id": prompt_id,
                "messages": entry["messages"],
                "expected": entry.get("expected") # Optional
            })
        elif "turns" in entry and isinstance(entry["turns"], list):
             # Further validation could be added for turn structure if needed
             validated_prompts.append({
                "id": prompt_id,
                "turns": entry["turns"]
                # Expected answers are within turns now
            })
        else:
             logging.warning(f"Skipping entry '{prompt_id}': Missing or invalid 'messages' or 'turns' field.")
             continue

    if not validated_prompts:
         logging.warning("No valid prompts or conversations were loaded.")

    source = f"file '{prompt_file_path}'" if prompt_file_path else "configuration data"
    logging.info(f"Loaded {len(validated_prompts)} valid prompts/conversations from {source}.")
    return validated_prompts
