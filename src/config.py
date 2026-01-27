import os

#DB ===================================================================================
DB_USERNAME = os.getenv("DB_USERNAME", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_PORT = os.getenv("DB_PORT", 5432)
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "postgres")

SQLALCHEMY_DB_URL = f"postgresql+psycopg2://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
#celery ===================================================================================
CELERY_BROKER_URL = os.getenv(
        "CELERY_BROKER_URL", "redis://localhost:6379")
CELERY_RESULT_BACKEND = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379")
CELERY_INCLUDE_TASKS = os.getenv(
        "CELERY_INCLUDE_TASKS", "0")
#Embedding Model ==========================================================================
EMBEDDING_MODEL_NAME=os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-code-v1")
HF_HOME=os.getenv("HF_HOME", "/usr/src/app/.hf")
HUGGINGFACE_HUB_CACHE=os.getenv("HUGGINGFACE_HUB_CACHE", "/usr/src/app/.hf/hub")
TRANSFORMERS_CACHE=os.getenv("TRANSFORMERS_CACHE", "/usr/src/app/.hf/transformers")
HF_TOKEN=os.getenv("HF_TOKEN")