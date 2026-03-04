# type: ignore[all]
import time

from typing import Any, Generator


from src.config import LLM_MODEL_NAME, HF_HOME
import threading

from typing import TYPE_CHECKING

from src.features.documentation_generator.constants import SYSTEM_PROMPT
from src.features.indexer.models import ChunkType
from src.features.documentation_generator.utils import split_huge_text

if TYPE_CHECKING:
    from transformers import (
        PreTrainedTokenizerBase,
        PreTrainedModel,
    )


_MODEL: Any = None
_MODEL_LOCK = threading.Lock()
_TOKENIZER = None
_TOKENIZER_LOCK = threading.Lock()


def get_llm_model() -> "PreTrainedModel":
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    global _MODEL
    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is None:
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
                device_map={"": 0} if device == "cuda" else None,
                quantization_config=bnb_config,
            )
            _MODEL.eval()
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
        return _TOKENIZER


# =======================================================================================
def create_prompt(
    chunk_type: ChunkType,
    file_path: str,
    signature: str | None = None,
    lang: str | None = None,
    content: str | None = None,
    sys_prompt: str | None = None,
    usr_prompt: str | None = None,
):

    parts = [
        f"Entity Type: {chunk_type.value}",
        f"File Path: {file_path}",
    ]

    if signature:
        parts.insert(1, f"Entity Name: {signature}")
    if lang:
        parts.insert(1, f"Programming Language: {lang}")

    parts.append(f"\nContent:\n{content}")

    USER_PROMPT = "\n".join(parts)

    messages = [
        {"role": "system", "content": sys_prompt if sys_prompt else SYSTEM_PROMPT},
        {"role": "user", "content": usr_prompt if usr_prompt else USER_PROMPT},
    ]

    return messages


CONTEXT_LIMIT = 1200
RESERVED_OUTPUT = 384
MAX_INPUT_TOKENS = CONTEXT_LIMIT - RESERVED_OUTPUT


def safe_prompt(tokenizer, text, max_tokens=MAX_INPUT_TOKENS):
    tokens = tokenizer(text, add_special_tokens=False).input_ids
    return len(tokens) <= max_tokens


def apply_chat_template(messages, tokenizer):
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    return text


def create_model_input(text, tokenizer, model):
    model_inputs = tokenizer(text, return_tensors="pt").to(model.device)
    return model_inputs


def generate_text(model_inputs, model, max_new_tokens: int = 512):
    import torch

    with torch.inference_mode():
        generated_ids = model.generate(**model_inputs, max_new_tokens=max_new_tokens)
    generated_ids = [
        out_ids[in_ids.shape[-1] :]
        for in_ids, out_ids in zip(model_inputs["input_ids"], generated_ids)
    ]
    return generated_ids


def decode_generated_text(generated_ids, tokenizer):
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return response


def generate_llm_response(
    tokenizer: Any,
    model: Any,
    chunk_type: ChunkType,
    file_path: str,
    signature: str | None = None,
    lang: str | None = None,
    content: str | None = None,
    sys_prompt: str | None = None,
    usr_prompt: str | None = None,
) -> str:
    prompt = create_prompt(
        file_path=file_path,
        content=content,
        usr_prompt=usr_prompt,
        sys_prompt=sys_prompt,
        signature=signature,
        chunk_type=chunk_type,
        lang=lang,
    )
    full_text = apply_chat_template(messages=prompt, tokenizer=tokenizer)
    print(f"full_text {full_text}")

    if safe_prompt(tokenizer=tokenizer, text=full_text):
        model_inputs = create_model_input(
            text=full_text, tokenizer=tokenizer, model=model
        )

        t0 = time.time()
        gen_ids = generate_text(
            model=model, model_inputs=model_inputs, max_new_tokens=512
        )
        dt = time.time() - t0
        out_tokens = gen_ids[0].shape[-1]
        print(
            "seconds:",
            round(dt, 3),
            "out_tokens:",
            out_tokens,
            "tok/s:",
            round(out_tokens / dt, 2),
        )
        return decode_generated_text(generated_ids=gen_ids, tokenizer=tokenizer)

    parts = split_huge_text(content)
    partial_summaries: list[str] = []

    for part in parts:
        part_prompt = create_prompt(
            file_path=file_path,
            content=part,
            usr_prompt=usr_prompt,
            sys_prompt=sys_prompt,
            signature=signature,
            chunk_type=chunk_type,
            lang=lang,
        )
        part_text = apply_chat_template(messages=part_prompt, tokenizer=tokenizer)
        print(f"part_text {part_text}")

        if not safe_prompt(tokenizer, part_text):
            subparts = split_huge_text(part, max_bytes=3_000)
            for sp in subparts:
                sp_prompt = create_prompt(
                    file_path=file_path,
                    content=sp,
                    usr_prompt=usr_prompt,
                    sys_prompt=sys_prompt,
                    signature=signature,
                    chunk_type=chunk_type,
                    lang=lang,
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
                        max_new_tokens=256,
                    )
                else:
                    sp_inputs = create_model_input(sp_text, tokenizer, model)
                    gen_ids = generate_text(
                        model=model,
                        model_inputs=sp_inputs,
                        max_new_tokens=256,
                    )
                partial_summaries.append(
                    decode_generated_text(generated_ids=gen_ids, tokenizer=tokenizer)
                )
            continue

        part_inputs = create_model_input(
            text=part_text, tokenizer=tokenizer, model=model
        )
        gen_ids = generate_text(
            model=model, model_inputs=part_inputs, max_new_tokens=256
        )
        partial_summaries.append(
            decode_generated_text(generated_ids=gen_ids, tokenizer=tokenizer)
        )


def stream_llm_response(
    tokenizer: Any,
    model: Any,
    chunk_type: ChunkType,
    file_path: str,
    signature: str | None = None,
    lang: str | None = None,
    content: str | None = None,
    sys_prompt: str | None = None,
    usr_prompt: str | None = None,
    max_new_tokens: int = 512,
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
        signature=signature,
        chunk_type=chunk_type,
        lang=lang,
    )
    full_text = apply_chat_template(messages=prompt, tokenizer=tokenizer)

    inputs = create_model_input(full_text, tokenizer, model)

    streamer = TextIteratorStreamer(
        tokenizer=tokenizer,
        skip_prompt=True,
        skip_special_tokens=True,
    )

    gen_kwargs = dict(
        **inputs,
        streamer=streamer,
        max_new_tokens=max_new_tokens,
        do_sample=(temperature > 0),
        temperature=temperature,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
    )

    t = threading.Thread(target=model.generate, kwargs=gen_kwargs, daemon=True)
    t.start()

    for text in streamer:
        if text:
            yield text
