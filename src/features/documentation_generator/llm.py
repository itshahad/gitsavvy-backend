# type: ignore [all]
from typing import Any
from src.config import LLM_MODEL_NAME, HF_HOME
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
                device_map="auto" if device == "cuda" else None,
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
def create_docs_generation_prompt(file_path: str, content: str):
    SYSTEM_PROMPT = """
    You are an expert technical documentation generator.

    You will receive content that may include source code, configuration, markdown, plain text, or mixed content.
    You MUST document only what is present in the provided content.

    Hard constraints:
    - Use only the provided content. Do NOT hallucinate.
    - If something is not explicitly defined, state: "Not explicitly defined in the provided content."
    - Output MUST be a single raw JSON object and NOTHING else.
    - Do NOT wrap output in markdown code fences (no ``` or ```json).
    - Do NOT include any text before or after the JSON object.
    - The first character of the output MUST be '{' and the last character MUST be '}'.
    - Do NOT add language labels.   

    JSON schema (MUST match exactly):
    {
    "short_summary": "1-2 sentences only.",
    "detailed_documentation": "Markdown documentation as a single string."
    }

    Rules for "short_summary":
    - MUST be a single string.
    - MUST be 1-2 sentences (no bullet points, no headings).

    Rules for "detailed_documentation":
    - MUST be a single string containing Markdown only (no nested JSON objects/arrays).
    - MUST start with a level-2 heading exactly: ## <name>
    - Do NOT add language labels or generic titles (e.g., no '# JavaScript Function Documentation').
    - Use only relevant headings/sections for the provided content.
    - If documenting a function/class, use sections like: ### Description, ### Parameters, ### Returns, ### Behavior, ### Edge Cases (only if applicable).
    - If documenting configuration, use sections like: ### Purpose, ### Key Fields, ### Notes (only if applicable).

    JSON encoding rules (IMPORTANT):
    - Do NOT include literal newline characters inside JSON strings. Use "\\n" for line breaks.
    - Any double quotes inside the Markdown MUST be escaped as "\\\"".
    - Backslashes must be escaped as "\\\\" when needed.

    Return ONLY the JSON object that matches the schema above.
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


CONTEXT_LIMIT = 8192
RESERVED_OUTPUT = 1024
MAX_INPUT_TOKENS = CONTEXT_LIMIT - RESERVED_OUTPUT


def safe_prompt(tokenizer, text, max_tokens=MAX_INPUT_TOKENS):
    tokens = tokenizer.encode(text)
    if len(tokens) > max_tokens:
        raise ValueError("input is too big")
    return len(tokens)


def create_model_input(messages, tokenizer, model):
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    safe_prompt(tokenizer=tokenizer, text=text)
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
