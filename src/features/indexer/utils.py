import os
import hashlib
from zipfile import ZipFile, ZipInfo
from pathlib import Path
from src.features.indexer.constants import *
from tree_sitter import Node
from sqlalchemy.orm import Session
from typing import TypeVar
from sqlalchemy.sql import Select

T = TypeVar("T")


def normalize_newlines(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


def get_repo_path(repo_name: str) -> Path:
    return Path(f"{REPOS_PATH}/{repo_name}.zip")


def get_file_complete_path(file_path: str, repo_name: str) -> str:
    return f"{REPOS_PATH}/{repo_name}/{file_path}"


def norm(p: str) -> str:
    return p.replace("\\", "/").lower()


def ext(file_path: str) -> str:
    _, ext = os.path.splitext(file_path)
    return ext.lower()


def lang_from_ext(file_ext: str):
    return EXT_TO_LANG.get(file_ext.lower())


def is_skipped(file_path: str) -> bool:
    p = norm(file_path)
    if p.endswith("/"):
        return True
    if any(marker in p for marker in SKIP_DIR_MARKERS):
        return True
    if ext(p) in SKIP_EXT:
        return True
    return False


def is_selected(file_path: str) -> bool:
    p = norm(file_path)

    base = os.path.basename(p)
    if base in IMPORTANT_FILES_EXACT:
        return True

    if any(p.startswith(prefix) for prefix in IMPORTANT_PREFIXES):
        return True

    if ext(p) in AST_LANG_EXT or ext(p) in TEXT_LANG_EXT:
        return True

    return False


def find_body(node: Node) -> Node | None:
    for hint in BODY_FIELD_HINTS:
        b = node.child_by_field_name(hint)
        if b is not None:
            return b

    for ch in node.named_children:
        if ch.type in BODY_NODE_TYPES:
            return ch

    return None


def is_block(node: Node, lang: str | None = None) -> bool:
    return (
        (node.type in BLOCK_TYPES)
        or is_function(node, lang=lang)
        or is_class(node, lang=lang)
    )


def is_function(node: Node, lang: str | None = None) -> bool:
    if not lang:
        return False
    return node.type in FUNCTION_NODE_TYPES.get(lang, set())


def is_class(node: Node, *, lang: str | None = None) -> bool:
    if not lang:
        return False
    return node.type in CLASS_NODE_TYPES.get(lang, set())


def node_text(src: bytes, node: Node) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def node_line_count(node: Node) -> int:
    return node.end_point[0] - node.start_point[0] + 1


def slice_text(src: bytes, a: int, b: int) -> str:
    return src[a:b].decode("utf-8", errors="replace")


def node_signature(src: bytes, node: Node):
    body = find_body(node)
    if body:

        end = body.start_byte
        if src[end : end + 1] == b"{":
            end += 1

        return slice_text(src, node.start_byte, end)
    else:
        return node_text(src, node)


def block_placeholder(src: bytes, node: Node) -> str:
    text = node_text(src, node)
    first_line = (text.splitlines()[0].strip() if text else node.type)[:120]
    start = node.start_point[0] + 1
    end = node.end_point[0] + 1
    return f"\n/* CHILD: {node.type} ({start} - {end}) {first_line} */\n"


def unwrap_node(wrapper: Node, lang: str | None = None):
    if wrapper.type == "decorated_definition":
        inner = wrapper.child_by_field_name("definition")
        if inner and (is_function(inner, lang=lang) or is_class(inner, lang=lang)):
            return inner

    for child in wrapper.named_children:
        if is_function(child, lang=lang) or is_class(child, lang=lang):
            return child
    return None


def is_binary(zip_file: ZipFile, info: ZipInfo, sample_size: int = 4096):
    with zip_file.open(info) as f:
        data = f.read(sample_size)

        for magic in BINARY_FILE_MAGICS:
            if data.startswith(magic):
                return True
    return False


def hash_file_content(zip_file: ZipFile, info: ZipInfo):
    BUF_SIZE = 65536
    content_hash = hashlib.sha1()
    with zip_file.open(info, "r") as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            content_hash.update(data)
    return content_hash.hexdigest()


def hash_text(text: str):
    normalized = text.replace("\r\n", "\n").strip()
    content_hash = hashlib.sha1()
    content_hash.update(normalized.encode("utf-8", errors="replace"))
    return content_hash.hexdigest()


def validate_sha(v: str) -> str:
    if not SHA1_RE.match(v):
        raise ValueError("SHA1 must be a 40-char hex")
    return v


def dict_to_text(d: dict[str, str]) -> str:
    return "\n".join(f"{k}: {v}" for k, v in d.items())


def get_item_from_db(session: Session, stmt: Select[tuple[T]]) -> T | None:
    result = session.execute(stmt).first()
    return result[0] if result else None
