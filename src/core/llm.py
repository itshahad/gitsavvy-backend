# type: ignore [all]
from typing import Any, Generator
import threading
import gc
from typing import TYPE_CHECKING

from src.config import LLM_MODEL_NAME, HF_HOME
from src.features.documentation_generator.constants import SYSTEM_PROMPT
from src.features.documentation_generator.utils import split_huge_text

if TYPE_CHECKING:
    from transformers import (
        PreTrainedTokenizerBase,
        PreTrainedModel,
        TextIteratorStreamer,
    )

_MODEL: Any = None
_MODEL_LOCK = threading.Lock()
_TOKENIZER = None
_TOKENIZER_LOCK = threading.Lock()


def _cleanup_cuda() -> None:
    try:
        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _print_cuda_mem(prefix: str = "") -> None:
    try:
        import torch

        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**2
            reserved = torch.cuda.memory_reserved() / 1024**2
            print(
                f"{prefix} CUDA allocated={allocated:.1f} MiB reserved={reserved:.1f} MiB"
            )
    except Exception:
        pass


def get_llm_model() -> "PreTrainedModel":
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    if device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.backends.cudnn.benchmark = True

    global _MODEL
    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is None:
            if device == "cuda":
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16,
                )

                _MODEL = AutoModelForCausalLM.from_pretrained(
                    LLM_MODEL_NAME,
                    trust_remote_code=True,
                    cache_dir=HF_HOME,
                    low_cpu_mem_usage=True,
                    torch_dtype=dtype,
                    device_map={"": 0},
                    quantization_config=bnb_config,
                    # attn_implementation="sdpa",
                )
            else:
                _MODEL = AutoModelForCausalLM.from_pretrained(
                    LLM_MODEL_NAME,
                    trust_remote_code=True,
                    cache_dir=HF_HOME,
                    low_cpu_mem_usage=True,
                    torch_dtype=dtype,
                )

            _MODEL.eval()

            try:
                _MODEL.generation_config.use_cache = True
            except Exception:
                pass

        return _MODEL


def get_llm_tokenizer() -> "PreTrainedTokenizerBase":
    from transformers import AutoTokenizer

    global _TOKENIZER
    if _TOKENIZER is not None:
        return _TOKENIZER

    with _TOKENIZER_LOCK:
        if _TOKENIZER is None:
            _TOKENIZER = AutoTokenizer.from_pretrained(
                LLM_MODEL_NAME,
                trust_remote_code=True,
                cache_dir=HF_HOME,
            )

            # IMPORTANT for decoder-only generation with padding
            _TOKENIZER.padding_side = "left"

            if _TOKENIZER.pad_token is None:
                _TOKENIZER.pad_token = _TOKENIZER.eos_token

            print("TOKENIZER padding_side =", _TOKENIZER.padding_side)
            print("TOKENIZER pad_token_id =", _TOKENIZER.pad_token_id)
            print("TOKENIZER eos_token_id =", _TOKENIZER.eos_token_id)

        return _TOKENIZER


# =======================================================================================
def create_prompt(
    chunk_type: Any | None = None,
    file_path: str | None = None,
    signature: str | None = None,
    lang: str | None = None,
    content: str | None = None,
    sys_prompt: str | None = None,
    usr_prompt: str | None = None,
):
    parts = [
        f"File Path: {file_path}",
    ]

    if chunk_type:
        parts.append(f"Entity Type: {chunk_type.value}")
    if signature:
        parts.append(f"Entity Name: {signature}")
    if lang:
        parts.append(f"Programming Language: {lang}")

    parts.append(f"\nContent:\n{content}")

    user_prompt = "\n".join(parts)

    messages = [
        {"role": "system", "content": sys_prompt if sys_prompt else SYSTEM_PROMPT},
        {"role": "user", "content": usr_prompt if usr_prompt else user_prompt},
    ]

    return messages


CONTEXT_LIMIT = 8192
RESERVED_OUTPUT = 1024
MAX_INPUT_TOKENS = 4096


def safe_prompt(tokenizer, text, max_tokens=MAX_INPUT_TOKENS) -> bool:
    """
    Accepts either:
      - text: str
      - text: list[str]   (for batching)
    Returns True only if ALL inputs are <= max_tokens.
    """
    if isinstance(text, list):
        for t in text:
            tokens = tokenizer(t, add_special_tokens=False).input_ids
            if len(tokens) > max_tokens:
                return False
        return True

    tokens = tokenizer(text, add_special_tokens=False).input_ids
    return len(tokens) <= max_tokens


def apply_chat_template(messages, tokenizer) -> str:
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )


def create_model_input(text, tokenizer, model):
    model_inputs = tokenizer(text, return_tensors="pt").to(model.device)
    return model_inputs


def create_model_inputs_batch(texts: list[str], tokenizer, model):
    """
    Batch tokenization with padding so we can do ONE model.generate call.
    NOTE: we keep truncation=False; caller must ensure safe_prompt() is true.
    """
    inputs = tokenizer(
        texts,
        return_tensors="pt",
        padding=True,
        truncation=False,
    ).to(model.device)
    return inputs


def generate_text(
    model_inputs,
    model,
    tokenizer=None,
    max_new_tokens: int = 128,
    temperature: float = 0.0,
    top_p: float = 0.9,
    repetition_penalty: float = 1.05,
):
    import torch

    gen_kwargs = dict(
        **model_inputs,
        max_new_tokens=max_new_tokens,
        use_cache=True,
        do_sample=(temperature > 0),
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        num_beams=1,
    )

    if temperature > 0:
        gen_kwargs["temperature"] = temperature

    if tokenizer is not None:
        if getattr(model.generation_config, "pad_token_id", None) is None:
            try:
                model.generation_config.pad_token_id = tokenizer.eos_token_id
            except Exception:
                pass
        gen_kwargs["pad_token_id"] = model.generation_config.pad_token_id

    with torch.inference_mode():
        out = model.generate(**gen_kwargs)

    input_width = model_inputs["input_ids"].shape[1]
    result = [out_row[input_width:] for out_row in out]

    del out
    del gen_kwargs
    del model_inputs
    _cleanup_cuda()

    return result


def generate_text_batch(
    model_inputs,
    model,
    tokenizer,
    max_new_tokens: int = 128,
    temperature: float = 0.0,
    top_p: float = 0.9,
    repetition_penalty: float = 1.05,
) -> list[str]:
    """
    Returns list[str] outputs aligned with the batch order.
    """
    import torch
    import time

    if getattr(model.generation_config, "pad_token_id", None) is None:
        try:
            model.generation_config.pad_token_id = tokenizer.eos_token_id
        except Exception:
            pass

    lengths = model_inputs["attention_mask"].sum(dim=1).tolist()
    print("batch prompt lengths:", lengths)
    print("batch size:", len(lengths))
    print("batch max len:", max(lengths) if lengths else 0)
    print("batch min len:", min(lengths) if lengths else 0)
    print("max_new_tokens:", max_new_tokens)
    _print_cuda_mem("[BEFORE GENERATE]")

    gen_kwargs = dict(
        **model_inputs,
        max_new_tokens=max_new_tokens,
        use_cache=True,
        do_sample=(temperature > 0),
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        num_beams=1,
        pad_token_id=model.generation_config.pad_token_id,
    )

    if temperature > 0:
        gen_kwargs["temperature"] = temperature

    start = time.perf_counter()
    with torch.inference_mode():
        out = model.generate(**gen_kwargs)
    print(f"generate_text_batch took {time.perf_counter() - start:.2f}s")

    # For padded batch generation, continuation starts after full padded width
    input_width = model_inputs["input_ids"].shape[1]

    outputs: list[str] = []
    for i in range(out.shape[0]):
        gen_ids = out[i, input_width:]
        outputs.append(tokenizer.decode(gen_ids, skip_special_tokens=True))

    del out
    del gen_kwargs
    del model_inputs
    _cleanup_cuda()
    _print_cuda_mem("[AFTER GENERATE]")

    return outputs


def decode_generated_text(generated_ids, tokenizer) -> str:
    text = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    del generated_ids
    return text


def generate_llm_response(
    tokenizer: Any,
    model: Any,
    chunk_type: Any,
    lang: str | None = None,
    signature: str | None = None,
    content: str | None = None,
    file_path: str | None = None,
    sys_prompt: str | None = None,
    usr_prompt: str | None = None,
) -> str:
    prompt = create_prompt(
        chunk_type=chunk_type,
        lang=lang,
        signature=signature,
        file_path=file_path,
        content=content,
        usr_prompt=usr_prompt,
        sys_prompt=sys_prompt,
    )
    full_text = apply_chat_template(messages=prompt, tokenizer=tokenizer)

    if safe_prompt(tokenizer=tokenizer, text=full_text):
        model_inputs = create_model_input(
            text=full_text, tokenizer=tokenizer, model=model
        )
        gen_ids = generate_text(
            model=model,
            model_inputs=model_inputs,
            tokenizer=tokenizer,
            max_new_tokens=128,
            temperature=0.0,
        )
        return decode_generated_text(generated_ids=gen_ids, tokenizer=tokenizer)

    # Too big: chunk into parts and summarize; then merge summaries into one final answer
    parts = split_huge_text(content or "")
    partial_summaries: list[str] = []

    for part in parts:
        part_prompt = create_prompt(
            file_path=file_path,
            content=part,
            chunk_type=chunk_type,
            lang=lang,
            signature=signature,
            sys_prompt=sys_prompt,
        )
        part_text = apply_chat_template(messages=part_prompt, tokenizer=tokenizer)

        if not safe_prompt(tokenizer, part_text):
            subparts = split_huge_text(part, max_bytes=3_000)
            for sp in subparts:
                sp_prompt = create_prompt(
                    file_path=file_path,
                    content=sp,
                    chunk_type=chunk_type,
                    lang=lang,
                    signature=signature,
                    sys_prompt=sys_prompt,
                )
                sp_text = apply_chat_template(messages=sp_prompt, tokenizer=tokenizer)

                if not safe_prompt(tokenizer=tokenizer, text=sp_text):
                    sp_ids = tokenizer(
                        sp_text,
                        return_tensors="pt",
                        truncation=True,
                        max_length=MAX_INPUT_TOKENS,
                    ).to(model.device)
                    gen_ids = generate_text(
                        model=model,
                        model_inputs=sp_ids,
                        tokenizer=tokenizer,
                        max_new_tokens=96,
                        temperature=0.0,
                    )
                else:
                    sp_inputs = create_model_input(sp_text, tokenizer, model)
                    gen_ids = generate_text(
                        model=model,
                        model_inputs=sp_inputs,
                        tokenizer=tokenizer,
                        max_new_tokens=96,
                        temperature=0.0,
                    )

                partial_summaries.append(
                    decode_generated_text(generated_ids=gen_ids, tokenizer=tokenizer)
                )
            continue

        part_inputs = create_model_input(
            text=part_text, tokenizer=tokenizer, model=model
        )
        gen_ids = generate_text(
            model=model,
            model_inputs=part_inputs,
            tokenizer=tokenizer,
            max_new_tokens=96,
            temperature=0.0,
        )
        partial_summaries.append(
            decode_generated_text(generated_ids=gen_ids, tokenizer=tokenizer)
        )

    merged_content = "\n\n".join(partial_summaries).strip()

    merge_usr_prompt = (
        "You will receive multiple partial summaries of the same code entity. "
        "Merge them into ONE final, coherent documentation output. "
        "Avoid repetition. Preserve important details (args/returns/behavior/side-effects)."
    )

    merge_prompt = create_prompt(
        chunk_type=chunk_type,
        lang=lang,
        signature=signature,
        file_path=file_path,
        content=merged_content,
        sys_prompt=sys_prompt,
        usr_prompt=merge_usr_prompt,
    )
    merge_text = apply_chat_template(messages=merge_prompt, tokenizer=tokenizer)

    if safe_prompt(tokenizer=tokenizer, text=merge_text):
        merge_inputs = create_model_input(
            text=merge_text, tokenizer=tokenizer, model=model
        )
        merge_ids = generate_text(
            model=model,
            model_inputs=merge_inputs,
            tokenizer=tokenizer,
            max_new_tokens=160,
            temperature=0.0,
        )
        return decode_generated_text(generated_ids=merge_ids, tokenizer=tokenizer)

    return merged_content


def generate_llm_responses_batch(
    tokenizer: Any,
    model: Any,
    requests: list[dict[str, Any]],
    batch_size: int = 1,
    max_new_tokens: int = 128,
    temperature: float = 0.0,
    top_p: float = 0.9,
    repetition_penalty: float = 1.05,
) -> list[str]:
    """
    Batch API for your docs generator.

    Each request dict can contain:
      chunk_type, lang, signature, content, file_path, sys_prompt, usr_prompt
    Returns list[str] aligned with input order.

    If an item is too large for MAX_INPUT_TOKENS, it falls back to generate_llm_response()
    for that item (your existing splitting logic).
    """
    results: list[str] = [""] * len(requests)

    i = 0
    while i < len(requests):
        batch = requests[i : i + batch_size]

        texts: list[str] = []
        idx_map: list[int] = []
        fallback: list[tuple[int, dict[str, Any]]] = []

        for j, req in enumerate(batch):
            prompt = create_prompt(
                chunk_type=req.get("chunk_type"),
                lang=req.get("lang"),
                signature=req.get("signature"),
                file_path=req.get("file_path"),
                content=req.get("content"),
                sys_prompt=req.get("sys_prompt"),
                usr_prompt=req.get("usr_prompt"),
            )
            full_text = apply_chat_template(messages=prompt, tokenizer=tokenizer)

            if safe_prompt(tokenizer=tokenizer, text=full_text):
                texts.append(full_text)
                idx_map.append(i + j)
            else:
                fallback.append((i + j, req))

        if texts:
            model_inputs = create_model_inputs_batch(
                texts=texts, tokenizer=tokenizer, model=model
            )
            outs = generate_text_batch(
                model_inputs=model_inputs,
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
            )
            for k, out_text in enumerate(outs):
                results[idx_map[k]] = out_text

            del outs
            _cleanup_cuda()

        for idx, req in fallback:
            results[idx] = generate_llm_response(
                tokenizer=tokenizer,
                model=model,
                chunk_type=req.get("chunk_type"),
                lang=req.get("lang"),
                signature=req.get("signature"),
                content=req.get("content"),
                file_path=req.get("file_path"),
                sys_prompt=req.get("sys_prompt"),
                usr_prompt=req.get("usr_prompt"),
            )
            _cleanup_cuda()

        i += batch_size

    return results


def stream_llm_response(
    tokenizer: Any,
    model: Any,
    content: str | None = None,
    file_path: str | None = None,
    sys_prompt: str | None = None,
    usr_prompt: str | None = None,
    max_new_tokens: int = 160,
    temperature: float = 0.2,
    top_p: float = 0.9,
    repetition_penalty: float = 1.05,
) -> Generator[str, None, None]:
    from transformers import TextIteratorStreamer

    prompt = create_prompt(
        file_path=file_path,
        content=content,
        usr_prompt=usr_prompt,
        sys_prompt=sys_prompt,
    )
    full_text = apply_chat_template(messages=prompt, tokenizer=tokenizer)

    if not safe_prompt(tokenizer=tokenizer, text=full_text):
        inputs = tokenizer(
            full_text,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_INPUT_TOKENS,
        ).to(model.device)
    else:
        inputs = create_model_input(full_text, tokenizer, model)

    streamer = TextIteratorStreamer(
        tokenizer=tokenizer,
        skip_prompt=True,
        skip_special_tokens=True,
    )

    pad_token_id = getattr(model.generation_config, "pad_token_id", None)
    if pad_token_id is None:
        try:
            model.generation_config.pad_token_id = tokenizer.eos_token_id
        except Exception:
            pass
        pad_token_id = getattr(model.generation_config, "pad_token_id", None)

    gen_kwargs = dict(
        **inputs,
        streamer=streamer,
        max_new_tokens=max_new_tokens,
        use_cache=True,
        do_sample=(temperature > 0),
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        num_beams=1,
        pad_token_id=pad_token_id,
    )

    if temperature > 0:
        gen_kwargs["temperature"] = temperature

    t = threading.Thread(target=model.generate, kwargs=gen_kwargs, daemon=True)
    t.start()

    for text in streamer:
        if text:
            yield text

    del inputs
    del gen_kwargs
    _cleanup_cuda()
