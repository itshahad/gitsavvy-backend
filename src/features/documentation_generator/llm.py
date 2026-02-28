# type: ignore [all]
from typing import Any

from src.config import LLM_MODEL_NAME, HF_HOME
import threading

from typing import TYPE_CHECKING

from src.features.documentation_generator.constants import SYSTEM_PROMPT
from src.features.documentation_generator.utils import split_huge_chunk

if TYPE_CHECKING:
    from transformers import PreTrainedTokenizerBase, PreTrainedModel


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
def create_docs_generation_prompt(
    file_path: str,
    content: str | None = None,
    sys_prompt: str | None = None,
    usr_prompt: str | None = None,
):
    USER_PROMPT = f"""
Generate documentation for the following content.

File Path: {file_path}

Content:
{content}
"""

    messages = [
        {"role": "system", "content": sys_prompt if sys_prompt else SYSTEM_PROMPT},
        {"role": "user", "content": usr_prompt if usr_prompt else USER_PROMPT},
    ]

    return messages


CONTEXT_LIMIT = 8192
RESERVED_OUTPUT = 1024
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
