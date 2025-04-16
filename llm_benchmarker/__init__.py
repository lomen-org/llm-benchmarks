"""
LLM Benchmarker SDK
"""
import logging
from .runner import run_benchmark

# Configure logging for the package
logging.getLogger(__name__).addHandler(logging.NullHandler())

__version__ = "0.1.0" # Initial version
__all__ = ["run_benchmark"] # Public API
