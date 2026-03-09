import hashlib
from pathlib import PurePosixPath
from src.features.indexer.constants import *
from tree_sitter import Node
from src.features.repositories.constants import REPOS_PATH
from src.models_loader import Outline


def normalize_repo_path(zip_entry: str) -> str:
    p = PurePosixPath(zip_entry)
    if len(p.parts) > 1:
        p = PurePosixPath(*p.parts[1:])
    else:
        return "root"

    return str(p)


def is_root_readme(zip_entry: str) -> bool:
    p = PurePosixPath(zip_entry)
    if len(p.parts) != 2:
        return False

    return p.name.lower() in {"readme.md", "readme.rst", "readme.txt", "readme"}


def module_from_path(path: str):
    # zipfile/parent_dir/file.ext
    parent = PurePosixPath(path).parent
    if parent == PurePosixPath("."):
        return None
    return str(parent)


def normalize_newlines(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


def get_file_complete_path(file_path: str, repo_name: str) -> str:
    return f"{REPOS_PATH}/{repo_name}/{file_path}"


def lang_from_ext(file_ext: str):
    return EXT_TO_LANG.get(file_ext.lower())


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


def hash_text(text: str):
    normalized = text.replace("\r\n", "\n").strip()
    content_hash = hashlib.sha1()
    content_hash.update(normalized.encode("utf-8", errors="replace"))
    return content_hash.hexdigest()


def dict_to_text(d: dict[str, str]) -> str:
    return "\n".join(f"{k}: {v}" for k, v in d.items())


def outline_to_dict(outline: Outline):
    data: dict[str, int | str] = {
        "start_byte": outline.start_byte,
        "end_byte": outline.end_byte,
        "content": outline.content,
        "type": outline.type.value,
    }

    return data
