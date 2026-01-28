import os
import hashlib
from zipfile import ZipFile, ZipInfo
from pathlib import Path
from src.features.indexer.constants import *


def get_repo_path(repo_name:str):
    return Path(f"{REPOS_PATH}/{repo_name}.zip")

def get_file_complete_path(file_path:str, repo_name: str) -> str:
    return f"{REPOS_PATH}/{repo_name}/{file_path}"

def norm(p: str) -> str:
    return p.replace("\\", "/").lower()

def ext(file_path: str) -> str:
    _, ext = os.path.splitext(file_path)
    return ext

def is_skipped(file_path:str) -> bool:
    p = norm(file_path)
    if any(marker in p for marker in SKIP_DIR_MARKERS) or ext(p) in SKIP_EXT or p.endswith("/"):
        return True
    return False

def is_selected(file_path:str) -> bool:
    p = norm(file_path)
    if any(marker in p for marker in IMPORTANT_PREFIXES) or ext(p) in CODE_EXT:
        return True
    return False

def find_body(node):
    hints = ["body", "block", "members", "suite"]
    for hint in hints:
        b = node.child_by_field_name(hint)
        if b is not None: 
            return b
    return None

def is_function(node):
    t = node.type    
    if not any(h in t for h in FUNC_HINTS):
        return False
    return (
        any(d in t for d in DECL_HINTS)
        or t == "function_definition"
        or t == "method_definition"
        or t == "method_declaration"
        or t == "constructor_declaration"
        or t == "async_function_definition"
    )

def is_class(node):
    t = node.type
    if not any(h in t for h in CLASS_HINTS):
        return False
    return (
        any(d in t for d in DECL_HINTS)
        or t.endswith(SPEC_SUFFIX)
        or t in ("class_definition", "class_declaration", "interface_declaration")
    )

def node_text(src: bytes, node):
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

def slice_text(src: bytes, a: int, b: int) -> str:
    return src[a:b].decode("utf-8", errors="replace")

def node_signature(src: bytes, node):
    body = find_body(node)
    if body:
        return slice_text(src, node.start_byte, body.start_byte)
    else:
        return node_text(src, node)

def unwrap_function(wrapper):
    for child in wrapper.children:
        if is_function(child):
            return child
    return None

def is_binary(zip_file: ZipFile, info :ZipInfo, sample_size: int=4096):
    with zip_file.open(info) as f:
        data = f.read(sample_size)
        
        for magic in BINARY_FILE_MAGICS:
            if data.startswith(magic):
                return True   
    return False

def hash_file_content(zip_file: ZipFile, info :ZipInfo):
    BUF_SIZE = 65536
    content_hash = hashlib.sha1()
    with zip_file.open(info, "r") as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            content_hash.update(data)
    return content_hash.hexdigest()

def hash_text(text:str):
    normalized = text.replace("\r\n", "\n").strip()
    content_hash = hashlib.sha1()
    content_hash.update(normalized.encode("utf-8", errors="replace"))
    return content_hash.hexdigest()

def validate_sha(v: str) -> str:
    if not SHA1_RE.match(v):
        raise ValueError("SHA1 must be a 40-char hex")
    return v

def dict_to_text(d: dict) -> str:
    return "\n".join(f"{k}: {v}" for k , v in d.items())


def get_item_from_db(session, stmt) -> bool:
    result = session.execute(stmt).first()
    if result is not None:
        return result[0]
    else: 
        return None