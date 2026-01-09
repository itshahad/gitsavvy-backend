import requests , zipfile, io
import os
from pathlib import Path

API_URL = "https://api.github.com/"
GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_API_TOKEN}" 
}

def get_repo_metadata(owner:str, repo_name:str) -> str:
    r = requests.get(f"{API_URL}repos/{owner}/{repo_name}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def download_repo(owner, repo_name, branch_name="main") -> str:
    file_path = Path(f"repos/{repo_name}.zip")
    file_path.parent.mkdir(parents=True)
    r = requests.get(f"{API_URL}repos/{owner}/{repo_name}/zipball/{branch_name}", headers=HEADERS)
    r.raise_for_status()
    with open(file_path, mode="wb") as file:
        file.write(r.content)
    return str(file_path)


PROCESSABLE_FILE_EXTENSIONS = [
    # Source code
    ".py", ".js", ".ts", ".java", ".go", ".rb", ".php",
    ".rs", ".cpp", ".c", ".h", ".hpp", ".cs",
    ".swift", ".kt", ".scala", ".dart",
    ".jsx", ".tsx", ".vue", ".svelte",
    ".sh", ".bash", ".zsh", ".ps1",

    # Documentation
    ".md", ".rst", ".txt", ".adoc",

    # Config / metadata
    ".yml", ".yaml", ".json", ".toml", ".ini",
    ".cfg", ".env", ".properties",
]


def isSelected(file_path:str) -> bool:
    splitted = file_path.split(".")
    print(splitted)


