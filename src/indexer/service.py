import requests
from pathlib import Path
from zipfile import ZipFile
from tree_sitter_language_pack import get_parser
from .constants import *
from .config import *
from .utils import *

#==================================================================================================
#Github:
def get_repo_metadata(owner:str, repo_name:str) -> str:
    r = requests.get(f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}", headers=headers())
    r.raise_for_status()
    return r.json()

def download_repo(owner, repo_name, branch_name="main") -> str:
    file_path = Path(f"{REPOS_PATH}/{repo_name}.zip")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/zipball/{branch_name}", headers=headers())
    r.raise_for_status()
    with open(file_path, mode="wb") as file:
        file.write(r.content)
    return str(file_path)

#==================================================================================================
#file selection:
def select_repo_files(zip_file_path: str, repo_name, max_size:int=200_000): # 200KB per file
    selected_files = []
    extract_dir = Path(f"{REPOS_PATH}/{repo_name}")

    with ZipFile(zip_file_path, "r") as zip:
        for info in zip.infolist():
            print(info)
            if info.is_dir() or info.file_size > max_size:
                continue

            if not is_skipped(info.filename) and is_selected(info.filename):
                selected_files.append(info.filename)

        for path in selected_files:
            zip.extract(path, extract_dir)
    return selected_files
#==================================================================================================
#files chunking:
def chunk_text_files(file_path: str, chunk_size= 100, overlapping=20):
    if (overlapping >= chunk_size):
        raise ValueError("overlapping value must be less than chunk_size")
    
    chunks = []

    with open(file_path, "r") as f:
        lines = f.readlines()
    
    step = chunk_size - overlapping

    for i in range(0, len(lines), step):
        chunk = lines[i: i + chunk_size]
        chunks.append(chunk)
    
    return chunks
#--------------------------------------------------------------------------------------------------
#code files chunking:
def build_class_summary(src: bytes, node):
    parts = []

    body = find_body(node)

    header = slice_text(src, node.start_byte, body.start_byte) if body else node_text(src, node)
    parts.append(header.strip())

    simple_contents = []
    methods = []

    if body:
        for child in body.children:
            if is_function(child):
                methods.append(method_signature(src, child))
                continue

            wrapped_function = unwrap_function(child)
            if wrapped_function:
                methods.append(method_signature(src, wrapped_function))
                continue

            # if this node is just a wrapper and has children, don’t treat it as a class member itself let recursion handle its children
            if not child.is_named and child.children:
                continue
            
            content = node_text(src, child).strip()
            simple_contents.append(content)
    if simple_contents:
        parts.append("\nMembers/Comments:\n+" + "\n".join(f"- {m}" for m in simple_contents))
    if methods:
        parts.append("\nMethods:\n+" + "\n".join(f"- {m}" for m in methods))
    return "\n".join(parts).strip()

def build_file_summary(src: bytes, root):
    parts = []

    for child in root.children:
        if is_class(child) or is_function(child):
            break

        text = node_text(src, child)
        if not text:
            continue
        parts.append(text)
    return "\n".join(parts).strip() 


def visit_node(node, src: bytes, chunks_list: list):
    is_fn = is_function(node)
    is_cls = is_class(node)

    if is_fn:
        chunks_list.append(
            {
                "type": "function",
                "start_line": node.start_point[0]+1,
                "end_line": node.end_point[0]+1,
                "code_text": node_text(src, node),
                "node_type": node.type
            }
        )
    elif is_cls:
        chunks_list.append(
            {
                "type": "class",
                "start_line": node.start_point[0]+1,
                "end_line": node.end_point[0]+1,
                "code_text": build_class_summary(src, node),
                "node_type": node.type
            }
        )
    for child in node.children:
        visit_node(child, src, chunks_list)

def chunk_code_files(file_path: str):
    chunks = []
    file_bytes = Path(file_path).read_bytes()
    lang = "python"
    parser = get_parser(language_name=lang)

    tree = parser.parse(file_bytes)
    root = tree.root_node

    chunks.append(build_file_summary(file_bytes, root))
    visit_node(root, file_bytes, chunks)
        
    return chunks
#--------------------------------------------------------------------------------------------------
