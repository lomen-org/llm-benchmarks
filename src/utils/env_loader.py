import os
from dotenv import load_dotenv

def load_env_vars():
    load_dotenv()

def get_env(key, default=None):
    return os.getenv(key, default)