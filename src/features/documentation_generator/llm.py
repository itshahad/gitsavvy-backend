# type: ignore [all]
from typing import Any
from src.config import LLM_MODEL_NAME
import threading

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from transformers import PreTrainedTokenizerBase, PreTrainedModel


_MODEL: Any = None
_MODEL_LOCK = threading.Lock()
_TOKENIZER = None
_TOKENIZER_LOCK = threading.Lock()


def get_llm_model() -> "PreTrainedModel":
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
                LLM_MODEL_NAME,
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
                LLM_MODEL_NAME,
                trust_remote_code=True,
                cache_dir=HF_HOME,
            )
        return _TOKENIZER


# =======================================================================================
def create_docs_generation_prompt(file_path, content):
    SYSTEM_PROMPT = """
        You are an expert technical documentation generator.

        The provided content may include:
        - Source code (functions, classes, methods)
        - Configuration files (JSON, YAML, TOML)
        - Markdown or README files
        - Plain text
        - Mixed content

        Adapt the documentation style based on the type of content:
        - If it is executable code, document structure and behavior.
        - If it is configuration, document fields and their purpose.
        - If it is markdown or plain text, summarize structure and main ideas.
        - If it is mixed, explain both structure and behavior.

        Use only the provided content.
        Do not hallucinate missing information.
        If something is not explicitly defined, state that clearly.
        Return structured Markdown.
        Begin with a short 1-2 sentence summary.
        Return ONLY valid JSON:
        {
        "short_summary": "...",
        "detailed_documentation": "..."
        }
    """

    USER_PROMPT = f"""
        Generate documentation for the following content.

        File Path: {file_path}

        Content:
        ```text
        {content}
    """

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT},
    ]

    return messages


def create_model_input(messages, tokenizer):
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    return model_inputs


def generate_text(model_inputs, model):
    generated_ids = model.generate(**model_inputs, max_new_tokens=512)
    generated_ids = [
        output_ids[len(input_ids) :]
        for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ]
    return generated_ids


def decode_generated_text(generated_ids, tokenizer):
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return response
