"""Runtime configuration, read from environment variables / backend/.env."""
import os

from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4").strip()
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "600"))
