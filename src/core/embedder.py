# type: ignore [all]
from typing import Any
from src.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MAX_TOKENS,
    HF_HOME,
    OVERLAP_TOKENS,
    WINDOW_TOKENS,
    MIN_LAST_WINDOW_TOKENS,
)
import threading
from dataclasses import dataclass

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from transformers import PreTrainedTokenizerBase, PreTrainedModel


_MODEL: Any = None
_MODEL_LOCK = threading.Lock()
_TOKENIZER = None
_TOKENIZER_LOCK = threading.Lock()


def get_embedder_model() -> "PreTrainedModel":
    import torch
    from transformers import AutoModel

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    global _MODEL
    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is None:

            _MODEL = AutoModel.from_pretrained(
                EMBEDDING_MODEL_NAME,
                trust_remote_code=True,
                cache_dir=HF_HOME,
                low_cpu_mem_usage=True,
                torch_dtype=dtype,
            ).to(device)
            _MODEL.eval()
        return _MODEL


def get_tokenizer() -> "PreTrainedTokenizerBase":
    from transformers import AutoTokenizer

    global _TOKENIZER
    if _TOKENIZER is not None:
        return _TOKENIZER

    with _TOKENIZER_LOCK:
        if _TOKENIZER is None:
            _TOKENIZER = AutoTokenizer.from_pretrained(
                EMBEDDING_MODEL_NAME,
                trust_remote_code=True,
                cache_dir=HF_HOME,
            )
            _TOKENIZER.model_max_length = EMBEDDING_MAX_TOKENS
        return _TOKENIZER


@dataclass(frozen=True)
class WindowSpec:
    window_tokens: int = WINDOW_TOKENS
    overlap_tokens: int = OVERLAP_TOKENS
    min_last_window_tokens: int = MIN_LAST_WINDOW_TOKENS


# ================================================================================================================


def tokenize_text(tokenizer: Any, text: str) -> list[int]:
    enc = tokenizer(
        text,
        add_special_tokens=True,
        truncation=False,
        return_attention_mask=False,
        return_token_type_ids=False,
    )
    return enc["input_ids"]


def last_token_pool(last_hidden_states, attention_mask):
    import torch

    left_padding = attention_mask[:, -1].sum() == attention_mask.shape[0]
    if left_padding:
        return last_hidden_states[:, -1]
    else:
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = last_hidden_states.shape[0]
        return last_hidden_states[
            torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths
        ]


def batch_encoding(tokens_list, tokenizer, device):
    batch = tokenizer.pad(
        tokens_list,
        padding=True,
        return_tensors="pt",
        pad_to_multiple_of=8,  # expects tokens_list to be: list of dicts like [{ "input_ids": [...] }, ...]
    )
    # >> output:
    # batch = {
    #     "input_ids": tensor([[101, 2345, 678, ...]]),
    #     "attention_mask": tensor([[1, 1, 1, ...]])
    # }
    batch = {
        k: v.to(device) for k, v in batch.items()
    }  # must move tensors to same device the model is using
    return batch


def embed_texts(batch_dict, model):
    import torch
    import torch.nn.functional as F

    with torch.inference_mode():
        outputs = model(**batch_dict)

        embeddings = last_token_pool(
            outputs.last_hidden_state,
            batch_dict["attention_mask"],
        )

        embeddings = F.normalize(embeddings, p=2, dim=1)
        return embeddings


def make_token_windows(
    input_ids: list[int],
    *,
    spec: WindowSpec,
) -> list[list[int]]:
    w = spec.window_tokens
    ov = spec.overlap_tokens
    min_last = spec.min_last_window_tokens

    if w <= 0:
        raise ValueError("window_tokens must be > 0")
    if ov < 0:
        raise ValueError("overlap_tokens must be >= 0")
    if ov >= w:
        raise ValueError("overlap_tokens must be < window_tokens")

    n = len(input_ids)
    if n <= w:
        return [input_ids]

    step = w - ov
    windows: list[list[int]] = []
    start = 0

    while start < n:
        end = min(start + w, n)
        windows.append(input_ids[start:end])
        if end == n:
            break
        start += step

    # merge tiny last window to reduce extra compute
    if len(windows) >= 2 and len(windows[-1]) < min_last:
        merged = (windows[-2] + windows[-1])[-w:]
        windows = windows[:-2] + [merged]

    return windows


def infer_embedding(
    *,
    input_ids_list: list[list[int]],
    tokenizer: Any,
    model: Any,
    batch_encoding: Any,
    embed_texts: Any,
    device: Any,
    normalize: bool = True,
    batch_size: int = 16,
):
    import torch
    import torch.nn.functional as F

    outs: list[torch.Tensor] = []
    with torch.inference_mode():
        for i in range(0, len(input_ids_list), batch_size):
            batch_ids = input_ids_list[i : i + batch_size]

            batch_dict = batch_encoding(
                tokens_list=[{"input_ids": ids} for ids in batch_ids],
                device=device,
                tokenizer=tokenizer,
            )

            embs = embed_texts(batch_dict, model)
            outs.append(embs.detach().cpu())

    if not outs:
        return torch.empty((0, 0))

    return torch.cat(outs, dim=0)


# combine windows embeddings:
def mean_pool_embeddings(window_embs, normalize: bool = True):
    import torch.nn.functional as F

    if window_embs.ndim != 2 or window_embs.shape[0] == 0:
        raise ValueError("window_embs must be [W,H] with W>0")
    v = window_embs.mean(dim=0)
    if normalize:
        v = F.normalize(v.unsqueeze(0), p=2, dim=1).squeeze(0)
    return v


def embed_text(
    *,
    text: str,
    tokenizer: Any,
    model: Any,
    batch_encoding: Any,
    embed_texts: Any,
    device: Any,
    window_spec: WindowSpec = WindowSpec(512, 64, 64),
    batch_size: int = 16,
    normalize: bool = True,
) -> tuple[list[float], dict[str, Any]]:

    input_ids = tokenize_text(tokenizer=tokenizer, text=text)
    token_count = len(input_ids)
    is_safe = token_count <= EMBEDDING_MAX_TOKENS

    if is_safe:
        embs = infer_embedding(
            input_ids_list=[input_ids],
            tokenizer=tokenizer,
            model=model,
            batch_encoding=batch_encoding,
            embed_texts=embed_texts,
            device=device,
            normalize=normalize,
            batch_size=1,
        )
        vec = embs.squeeze(0).float().tolist()
        meta = {"token_count": token_count, "used_windowing": False, "num_windows": 1}
        return vec, meta

    windows = make_token_windows(input_ids, spec=window_spec)

    window_embs = infer_embedding(
        input_ids_list=windows,
        tokenizer=tokenizer,
        model=model,
        batch_encoding=batch_encoding,
        embed_texts=embed_texts,
        device=device,
        normalize=normalize,
        batch_size=batch_size,
    )

    pooled = mean_pool_embeddings(window_embs, normalize=normalize)
    vec = pooled.float().tolist()

    meta = {
        "token_count": token_count,
        "used_windowing": True,
        "num_windows": int(window_embs.shape[0]),
        "window_tokens": window_spec.window_tokens,
        "overlap_tokens": window_spec.overlap_tokens,
    }
    return vec, meta
