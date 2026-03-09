import os
from dotenv import load_dotenv

load_dotenv()

# DB ===================================================================================
DB_USERNAME = os.getenv("DB_USERNAME", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_PORT = os.getenv("DB_PORT", 5432)
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "postgres")

SQLALCHEMY_DB_URL = (
    f"postgresql+psycopg2://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


def get_sqlalchemy_db_url(host: str | None = None) -> str:
    DB_HOST = host if host is not None else os.getenv("DB_HOST", "localhost")
    return f"postgresql+psycopg2://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# celery ===================================================================================
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379")
CELERY_INCLUDE_TASKS = os.getenv("CELERY_INCLUDE_TASKS", "0")
# Hugging Face ==========================================================================
HF_HOME = os.getenv("HF_HOME", "/usr/src/app/.hf")
HUGGINGFACE_HUB_CACHE = os.getenv("HUGGINGFACE_HUB_CACHE", "/usr/src/app/.hf/hub")
TRANSFORMERS_CACHE = os.getenv("TRANSFORMERS_CACHE", "/usr/src/app/.hf/transformers")
HF_TOKEN = os.getenv("HF_TOKEN")
# Embedding Model ==========================================================================
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-code-v1")
EMBEDDING_MAX_TOKENS = int(os.getenv("EMBEDDING_MAX_TOKENS", 1024))
MAX_BYTES_NUM = int(os.getenv("MAX_BYTES_NUM", 8000))
OVERLAPPING_BYTES_NUM = int(os.getenv("OVERLAPPING_BYTES_NUM", 1000))
MIN_TAIL_BYTES = int(os.getenv("MIN_TAIL_BYTES", 1000))
WINDOW_TOKENS = int(os.getenv("WINDOW_TOKENS", 512))
OVERLAP_TOKENS = int(os.getenv("OVERLAP_TOKENS", 64))
MIN_LAST_WINDOW_TOKENS = int(os.getenv("MIN_LAST_WINDOW_TOKENS", 64))
# LLM Model ==========================================================================
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-Coder-3B-Instruct")
