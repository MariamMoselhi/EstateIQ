
# import os
# from pathlib import Path

# from dotenv import load_dotenv

# BASE_DIR = Path(__file__).resolve().parent.parent
# load_dotenv(BASE_DIR / ".env")

# DATA_DIR = BASE_DIR / "data"
# RAW_DATA_DIR = DATA_DIR / "raw"
# PROCESSED_DATA_DIR = DATA_DIR / "processed"
# CHROMA_DB_DIR = DATA_DIR / "chroma_db"
# OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")
# TOP_K = 3

# PORT = int(os.getenv("PORT", "10000"))
# APP_NAME = "EstateIQ"
# APP_VERSION = "1.0.0"

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "EstateIQ"
APP_VERSION = "1.0.0"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

class Settings(BaseSettings):
    openrouter_api_key: str = OPENROUTER_API_KEY
    openrouter_model: str = "dots-studio/dots-3-note-preview:free"        # your preferred model, tried first
    # Fallbacks, comma-separated, tried in order if the first model is rate-limited or retired
    openrouter_models: str = (
        "dots-studio/dots-3-note-preview:free,"
        "google/gemma-4-26b-a4b-it:free,"
        "google/gemma-4-31b-it:free,"
        "nvidia/nemotron-3.5-lightning:free,"
        "openrouter/free"
    )
    port: int = 10000
    chunks_path: str = str(BASE_DIR / "data/processed/chunks.jsonl")
    embeddings_path: str = str(BASE_DIR / "data/index/embeddings.npy")
    top_k: int = 5
    max_history_turns: int = 4
    rate_limit_per_min: int = 10

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    @property
    def models(self) -> list[str]:
        chain = ([self.openrouter_model] if self.openrouter_model else []) + self.openrouter_models.split(",")
        return list(dict.fromkeys(m.strip() for m in chain if m.strip()))


settings = Settings()

OPENROUTER_API_KEY = settings.openrouter_api_key
OPENROUTER_MODEL = settings.openrouter_model
TOP_K = settings.top_k
PORT = settings.port
