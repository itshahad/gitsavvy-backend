import hashlib
import os
from pathlib import Path
from typing import TypeVar
from zipfile import ZipFile, ZipInfo

from sqlalchemy.orm import Session
from sqlalchemy import Select

from src.features.repositories.constants import (
    AST_LANG_EXT,
    BINARY_FILE_MAGICS,
    IMPORTANT_FILES_EXACT,
    IMPORTANT_PREFIXES,
    REPOS_PATH,
    SKIP_EXT,
    TEXT_LANG_EXT,
)

T = TypeVar("T")


def get_repo_path(repo_name: str) -> Path:
    return Path(f"{REPOS_PATH}/{repo_name}.zip")


def get_item_from_db(session: Session, stmt: Select[tuple[T]]) -> T | None:
    result = session.execute(stmt).first()
    return result[0] if result else None


def norm(p: str) -> str:
    return p.replace("\\", "/").lower()


def ext(file_path: str) -> str:
    _, ext = os.path.splitext(file_path)
    return ext.lower()


def is_skipped(file_path: str) -> bool:
    p = norm(file_path)
    if p.endswith("/"):
        return True
    # if any(marker in p for marker in SKIP_DIR_MARKERS):
    #     return True
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
