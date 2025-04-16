import os
import logging
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from a .env file if it exists
# This allows users to set configuration in a .env file in the project root
# without modifying the code or setting system-wide environment variables.
dotenv_path = os.path.join(os.getcwd(), '.env') # Look for .env in the current working directory
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
    logging.debug(".env file found and loaded.")
else:
    logging.debug(".env file not found, relying on system environment variables.")


def get_env(var_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Retrieves an environment variable.

    Args:
        var_name: The name of the environment variable.
        default: The default value to return if the variable is not found.

    Returns:
        The value of the environment variable or the default value.
    """
    value = os.getenv(var_name, default)
    # Optional: Add logging for debugging which variables are being accessed
    # logging.debug(f"Accessing env var: {var_name}, Value: {'******' if 'KEY' in var_name else value}")
    return value
