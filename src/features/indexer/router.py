from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
import requests
from sqlalchemy.orm import Session
from tree_sitter_language_pack import get_parser
from src.database import get_db
from src.features.indexer.exceptions import RepoNotFoundError
from src.features.indexer.schemas import FileRead
from src.features.indexer.service import (
    build_file_summary,
    chunk_code_files,
    chunk_text_files,
    download_repo,
    get_repo_metadata,
    select_repo_files,
)
from src.features.indexer.tasks import indexer
from src.features.indexer.utils import ext, get_file_complete_path, lang_from_ext  # type: ignore


router = APIRouter()


@router.get("/")
def test(session: Session = Depends(get_db)):
    try:
        indexer.delay("Git-Savvy", "test")  # type: ignore
        return {"yay": "yay"}
        file = FileRead(
            repository_id=2,
            commit_sha="26c69dcc6b74480cfd3dbb73ecb942ad91ec5147",
            content_hash="97c74f376096d6bbe4e0dad56a9f77be235597c3",
            file_path="Git-Savvy-test-26c69dc/sample.tsx",
            id=26,
        )
        file_path = get_file_complete_path(file.file_path, "test")
        file_ext = ext(file_path)
        lang = lang_from_ext(file_ext)

        file_bytes = Path(file_path).read_bytes()
        if lang != None:
            parser = get_parser(language_name=lang)

            tree = parser.parse(file_bytes)
            root = tree.root_node
            return build_file_summary(
                src=file_bytes,
                root=root,
                repo_id=2,
                file=file,
                session=session,
                lang=lang,
            )
        # http = requests.session()
        # return chunk_code_files(session=session, file=file, repo_id=2, repo_name="test")
        # file = FileRead(
        #     repository_id=2,
        #     commit_sha="26c69dcc6b74480cfd3dbb73ecb942ad91ec5147",
        #     content_hash="97c74f376096d6bbe4e0dad56a9f77be235597c3",
        #     file_path="Git-Savvy-test-26c69dc/sample.toml",
        #     id=26,
        # )
        # return chunk_text_files(session=session, file=file, repo_id=2, repo_name="test")
        # return select_repo_files(
        #     session=session,
        #     commit_sha="26c69dcc6b74480cfd3dbb73ecb942ad91ec5147",
        #     repo_id=2,
        #     zip_file_path="repos/test.zip",
        #     repo_name="test",
        # )
        # return download_repo(http=http, owner="Git-Savvy", repo_name="test")
        # return get_repo_metadata(
        #     http=http, owner="Git-Savvy", repo_name="test", session=session
        # )
    except RepoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
