from src.config import EMBEDDING_MODEL_NAME, HF_HOME, HF_TOKEN
from sentence_transformers import SentenceTransformer
import threading


_MODELS = None
_LOCK = threading.Lock()

def get_embedder_model() -> SentenceTransformer:
    global _MODELS
    if _MODELS is not None:
        return _MODELS
    
    with _LOCK:
        if _MODELS is None:
            _MODELS = SentenceTransformer(EMBEDDING_MODEL_NAME, cache_folder=HF_HOME, device="cuda", token=HF_TOKEN)
        return _MODELS
    