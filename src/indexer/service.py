import requests
import os
from pathlib import Path
from zipfile import ZipFile

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


