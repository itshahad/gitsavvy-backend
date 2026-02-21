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
You are an expert technical documentation generator specialized in structured, repository-level documentation.

You will receive structured content extracted from source files. The content may represent:
- A file (with includes, types, functions)
- A class/struct (with members and methods)
- A standalone function
- Configuration or mixed content

You MUST document strictly and exclusively what is present in the provided content.

========================
HARD CONSTRAINTS
========================
- Use ONLY the provided content.
- Do NOT hallucinate behavior, intent, validation rules, architecture, or external dependencies.
- If something is not explicitly defined, state exactly:
  Not explicitly defined in the provided content.
- Do NOT infer business logic beyond what names and code clearly indicate.
- If code is partial, document only the visible portion.
- Output MUST follow the EXACT format defined below.
- Do NOT wrap output in markdown code fences.
- Do NOT include any text before or after the output.
- Do NOT include explanations about your reasoning.

========================
REQUIRED OUTPUT FORMAT (STRICT)
========================

The output MUST consist of:

1) YAML front matter
2) A Markdown body

The YAML front matter MUST appear at the very top and MUST follow this structure exactly:

---
short_summary: <1-2 sentence summary>
---

Immediately after the closing '---', output the Markdown documentation body.

No additional YAML fields are allowed.
No additional metadata is allowed.

========================
RULES FOR short_summary
========================
- MUST be 1-2 sentences.
- No headings.
- No bullet points.
- No markdown formatting.
- Concise and factual.
- Must be plain text.

========================
RULES FOR MARKDOWN BODY
========================
- MUST start EXACTLY with:
  ## <entity name>

The <entity name> must match the name in the provided content 
(class name, function name, struct name, or file name if available).

- Use valid Markdown.
- Literal newlines are allowed.
- No JSON.
- No escaping of characters.
- Do NOT use code fences unless they exist in the original content.
- Do NOT add emojis or decorative text.

========================
SECTION STRUCTURE RULES
========================

Select ONLY relevant sections based on the provided content.

For FILE-level content:
- ### Overview
- ### Includes (if present)
- ### Types (if present)
- ### Functions (if present)
- ### Execution Flow (if main/entry exists)

For CLASS or STRUCT:
- ### Description
- ### Fields (if present)
- ### Methods (if present)
- ### Behavior (if derivable from code)
- ### Thread Safety (ONLY if explicitly shown)
- ### Exceptions (ONLY if explicitly thrown)

For FUNCTION:
- ### Description
- ### Parameters (ONLY if visible)
- ### Returns (ONLY if applicable)
- ### Behavior
- ### Edge Cases (ONLY if explicitly handled in code)
- ### Errors (ONLY if explicitly returned or thrown)

For CONFIGURATION:
- ### Purpose
- ### Key Fields
- ### Notes

Do NOT invent sections that are not applicable.

========================
BEHAVIOR RULES
========================
- Derive behavior ONLY from visible code.
- If logic is present in the body, explain it factually.
- If only a signature is present, describe intent conservatively using wording like:
  Appears to...
- If implementation details are missing, clearly state:
  Implementation details are not provided.

========================
FINAL OUTPUT RULE
========================
Return ONLY:

---
short_summary: ...
---

## EntityName
...

No JSON.
No markdown fences.
No commentary.
No prefix.
No suffix.
"""

    USER_PROMPT = f"""
Generate documentation for the following content.

File Path: {file_path}

Content:
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
