import requests
import os
from pathlib import Path
from zipfile import ZipFile
from tree_sitter import Language, Parser
from tree_sitter_language_pack import get_binding, get_language, get_parser

API_URL = "https://api.github.com/"
GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_API_TOKEN}" 
}

REPOS_PATH = "repos"


def get_repo_metadata(owner:str, repo_name:str) -> str:
    r = requests.get(f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def download_repo(owner, repo_name, branch_name="main") -> str:
    file_path = Path(f"{REPOS_PATH}/{repo_name}.zip")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/zipball/{branch_name}", headers=HEADERS)
    r.raise_for_status()
    with open(file_path, mode="wb") as file:
        file.write(r.content)
    return str(file_path)


SKIP_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".mp4", ".mov", ".avi", ".mp3", ".wav",
    ".exe", ".dll", ".so", ".dylib",
    ".bin", ".class", ".jar",
}


SKIP_DIR_MARKERS = {
    "node_modules/", "dist/", "build/", ".next/", ".nuxt/",
    ".git/", ".idea/", ".vscode/",
    "coverage/", ".venv/", "venv/",
    "__pycache__/", ".pytest_cache/",
    "vendor/", "target/",
}

IMPORTANT_FILES_EXACT = {
    "readme.md", "readme.rst", "readme.txt",
    "license", "license.md", "license.txt",
    "contributing.md", "code_of_conduct.md", "security.md",
    "changelog.md",
    "pyproject.toml", "requirements.txt", "poetry.lock",
    "package.json", "pnpm-lock.yaml", "yarn.lock",
    "dockerfile", "compose.yml", "compose.yaml", ".env.example",
}

IMPORTANT_PREFIXES = (
    "docs/",
    ".github/",
    "src/",
    "app/",
    "lib/",
    "packages/",
)

CODE_EXT = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".kt", ".go", ".rs", ".c", ".cpp", ".h",
    ".cs", ".php", ".rb", ".swift",
    ".md", ".rst", ".txt",
    ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg",
    ".html", ".css", ".scss",
    ".sh", ".bat",
    ".sql",
}

def _norm(p: str) -> str:
    return p.replace("\\", "/").lower()

def _ext(file_path: str) -> str:
    _, ext = os.path.splitext(file_path)
    return ext

def is_skipped(file_path:str) -> bool:
    p = _norm(file_path)
    if any(marker in p for marker in SKIP_DIR_MARKERS) or _ext(p) in SKIP_EXT or p.endswith("/"):
        return True
    return False

def is_selected(file_path:str) -> bool:
    p = _norm(file_path)
    if any(marker in p for marker in IMPORTANT_PREFIXES) or _ext(p) in CODE_EXT:
        return True
    return False

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


FUNC_HINTS = ("function", "method", "constructor")
CLASS_HINTS = ("class", "interface", "struct", "trait", "protocol", "object")

DECL_HINTS = ("declaration", "definition", "item")
SPEC_SUFFIX = "_specifier"

def _is_function(node):
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

def _is_class(node):
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

def _slice_text(src: bytes, a: int, b: int) -> str:
    return src[a:b].decode("utf-8", errors="replace")

def _find_body(node):
    hints = ["body", "block", "members", "suite"]
    for hint in hints:
        b = node.child_by_field_name(hint)
        if b is not None: 
            return b
    return None

def _method_signature(src: bytes, node):
    body = _find_body(node)
    if body:
        return _slice_text(src, node.start_byte, body.start_byte)
    else:
        return node_text(src, node)

def _unwrap_function(wrapper):
    for child in wrapper.children:
        if _is_function(child):
            return child
    return None

def build_class_summary( src: bytes, node):
    parts = []

    body = _find_body(node)

    header = _slice_text(src, node.start_byte, body.start_byte) if body else node_text(src, node)
    parts.append(header.strip())

    simple_contents = []
    methods = []

    if body:
        for child in body.children:
            if _is_function(child):
                methods.append(_method_signature(src, child))
                continue

            wrapped_function = _unwrap_function(child)
            if wrapped_function:
                methods.append(_method_signature(src, wrapped_function))
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




def visit_node(node, src: bytes, chunks_list: list):
    is_fn = _is_function(node)
    is_cls = _is_class(node)

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

    visit_node(root, file_bytes, chunks)
        
    return chunks