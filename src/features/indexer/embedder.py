from src.config import EMBEDDING_MODEL_NAME, HF_HOME, HF_TOKEN
import threading


_MODELS = None
_LOCK = threading.Lock()

def get_embedder_model():
    from sentence_transformers import SentenceTransformer
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"

    global _MODELS
    if _MODELS is not None:
        return _MODELS
    
    with _LOCK:
        if _MODELS is None:
            _MODELS = SentenceTransformer(EMBEDDING_MODEL_NAME, cache_folder=HF_HOME, device=device, token=HF_TOKEN)
        return _MODELS
    