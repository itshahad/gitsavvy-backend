from src.config import EMBEDDING_MODEL_NAME, HF_HOME, HF_TOKEN, EMBEDDING_MAX_TOKENS
import threading


_MODELS = None
_MODEL_LOCK = threading.Lock()
_TOKENIZER = None
_TOKENIZER_LOCK = threading.Lock()

def get_embedder_model():
    import torch
    from transformers import AutoModel

    device = "cuda" if torch.cuda.is_available() else "cpu"

    global _MODELS
    if _MODELS is not None:
        return _MODELS
    
    with _MODEL_LOCK:
        if _MODELS is None:
            _MODELS = AutoModel.from_pretrained('BAAI/bge-code-v1', trust_remote_code=True).to(device)
            _MODELS.eval()
        return _MODELS
            
def get_tokenizer():
    from transformers import AutoTokenizer

    global _TOKENIZER
    if _TOKENIZER is not None:
        return _TOKENIZER
    
    with _TOKENIZER_LOCK:
        if _TOKENIZER is None:
            _TOKENIZER = AutoTokenizer.from_pretrained(EMBEDDING_MODEL_NAME, trust_remote_code=True)
        return _TOKENIZER


def last_token_pool(last_hidden_states, attention_mask):
    import torch

    left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
    if left_padding:
        return last_hidden_states[:, -1]
    else:
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = last_hidden_states.shape[0]
        return last_hidden_states[torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths]


def check_tokens(input_text: str, tokenizer): 
    enc = tokenizer(input_text, truncation= False, add_special_tokens=True)
    is_safe = len(enc["input_ids"]) <= EMBEDDING_MAX_TOKENS

    #maybe further splitting here and recall the function 
    return enc, is_safe

def batch_encoding(tokens_list, tokenizer, device):
    #device= next(model.parameters()).device
    batch = tokenizer.pad(
        tokens_list,
        padding=True,
        return_tensors="pt",
        pad_to_multiple_of=8
    )
    # >> output:
    # batch = {
    #     "input_ids": tensor([[101, 2345, 678, ...]]),
    #     "attention_mask": tensor([[1, 1, 1, ...]])
    # }   
    batch = {k: v.to(device) for k, v in batch.items()} #must move tensors to same device the model is using

    return batch

def embed_texts(batch_dict, model):
    import torch
    import torch.nn.functional as F

    
    with torch.no_grad():
        outputs = model(**batch_dict)
        embeddings = last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
        embeddings = F.normalize(embeddings, p=2, dim=1)

        return embeddings
    #store embed in db
