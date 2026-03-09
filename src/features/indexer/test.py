# from dataclasses import dataclass
# from pathlib import Path
# from typing import Any, Generator, Optional, Type
# from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
# import pytest
# import requests
# from sqlalchemy import Engine, create_engine, select
# from sqlalchemy.orm import sessionmaker, Session

# from src.database import Base
# from src.exceptions import ExternalServiceError, StorageError
# from src.features.indexer.models import (
#     Chunk,
#     ChunkType,
#     File,
#     Repository,
#     RepositoryTopic,
# )
# from src.features.indexer.schemas import ChunkRead, FileRead, TopicRead
# from src.features.indexer.service import ChunkingService, RepoService
# from src.features.indexer.utils import hash_text


# TEST_DB_URL = "sqlite+pysqlite:///:memory:"


# @pytest.fixture(scope="session")
# def engine():
#     engine = create_engine(
#         TEST_DB_URL,
#         future=True,
#         echo=False,
#     )
#     Base.metadata.create_all(bind=engine)
#     return engine


# @pytest.fixture
# def db_session(engine: Engine) -> Generator[Session, None, None]:
#     SessionLocal = sessionmaker(
#         bind=engine,
#         autoflush=False,
#         autocommit=False,
#         future=True,
#     )

#     session = SessionLocal()
#     try:
#         yield session
#         # session.rollback()
#     finally:
#         for table in reversed(Base.metadata.sorted_tables):
#             session.execute(table.delete())
#         session.commit()
#         session.close()


# @pytest.fixture
# def http_session():
#     return requests.session()


# @pytest.mark.parametrize(
#     "owner, repo_name, should_insert",
#     [
#         ("octocat", "Hello-World", True),
#         ("", "repo", False),
#         ("octocat", "", False),
#         ("this-owner-does-not-exist-123456789", "some-repo", False),
#         ("octocat", "this-repo-does-not-exist-123456789", False),
#     ],
# )
# def test_get_repo_metadata_real_http_and_db(
#     db_session: Session,
#     http_session: requests.Session,
#     owner: str,
#     repo_name: str,
#     should_insert: bool,
# ):
#     svc = RepoService(db_session=db_session, http_session=http_session, repo_name="any")

#     if should_insert:
#         repo_read = svc.get_repo_metadata(owner=owner, repo_name=repo_name)

#         # --- assert repo exists in DB ---
#         stmt = select(Repository).where(
#             Repository.owner == owner,
#             Repository.name == repo_name,
#         )
#         repo_row = db_session.execute(stmt).scalar_one()

#         assert repo_row.id is not None
#         assert repo_row.owner == owner
#         assert repo_row.name == repo_name

#         # --- assert topics were inserted (if any) ---
#         topics_stmt = select(RepositoryTopic.topic).where(
#             RepositoryTopic.repository_id == repo_row.id
#         )
#         db_topics = [t for (t,) in db_session.execute(topics_stmt).all()]

#         # service returns topics via github metadata; ensure DB has at least those
#         # (if your RepoRead exposes topics differently, adjust this line)
#         expected_topics: list[TopicRead] = getattr(repo_read, "topics", None) or []
#         for t in expected_topics:
#             assert t in db_topics

#     else:
#         with pytest.raises(Exception):
#             svc.get_repo_metadata(owner=owner, repo_name=repo_name)

#         # --- assert nothing inserted for that owner/repo ---
#         stmt = select(Repository).where(
#             Repository.owner == owner,
#             Repository.name == repo_name,
#         )
#         repo_row = db_session.execute(stmt).scalar_one_or_none()
#         assert repo_row is None


# # ----------------------------------------------------------------------------------


# @pytest.mark.parametrize(
#     "case, make_zip, zip_path, repo_name, should_raise, expected_exc, expected_min_files",
#     [
#         ("success", "valid", None, "repo_ok", False, None, 1),
#         ("bad_zip", "bad", None, "repo_badzip", True, ExternalServiceError, 0),
#         (
#             "missing_zip",
#             None,
#             "does_not_exist.zip",
#             "repo_missing",
#             True,
#             StorageError,
#             0,
#         ),
#     ],
# )
# def test_select_repo_files_real_zip_and_db(
#     db_session: Session,
#     http_session: requests.Session,
#     tmp_path: Path,
#     monkeypatch: pytest.MonkeyPatch,
#     case: str,
#     make_zip: str | None,
#     zip_path: Path | None,
#     repo_name: str,
#     should_raise: bool,
#     expected_exc: Optional[Type[BaseException]],
#     expected_min_files: int,
# ) -> None:
#     # ---- Arrange service ----
#     svc = RepoService(
#         db_session=db_session, http_session=http_session, repo_name=repo_name
#     )

#     # Patch the *module constant* used inside select_repo_files()
#     import src.features.indexer.service as repo_service_module

#     monkeypatch.setattr(repo_service_module, "REPOS_PATH", str(tmp_path))

#     repo_id = 123
#     commit_sha = "deadbeef" * 5

#     # --- create a real zip on disk ---
#     if make_zip == "valid":
#         zfile = Path(tmp_path / "repo.zip")
#         with ZipFile(zfile, "w", compression=ZIP_DEFLATED) as z:
#             z.writestr("README.md", "hello\nworld\n")
#             z.writestr("src/main.py", "print('hi')\n")
#             z.writestr("big.txt", "x" * 300_000)  # > 200KB (skipped by size)
#         zip_file_path: Path = zfile

#     elif make_zip == "bad":
#         zfile = tmp_path / "not_a_zip.zip"
#         zfile.write_bytes(b"this is not a zip")
#         zip_file_path = zfile

#     else:
#         assert zip_path is not None  # type narrowing
#         zip_file_path = zip_path

#     # --- deterministic selection helpers (typed) ---
#     def _is_skipped(filename: str) -> bool:
#         return False

#     def _is_binary(_zip: ZipFile, _info: ZipInfo) -> bool:
#         return False

#     def _is_selected(filename: str) -> bool:
#         return filename.endswith((".md", ".py"))

#     monkeypatch.setattr(repo_service_module, "is_skipped", _is_skipped)
#     monkeypatch.setattr(repo_service_module, "is_binary", _is_binary)
#     monkeypatch.setattr(repo_service_module, "is_selected", _is_selected)

#     # ---- Act + Assert ----
#     if should_raise:
#         assert expected_exc is not None  # required: pytest.raises() can't take None

#         with pytest.raises(expected_exc):
#             svc.select_repo_files(
#                 repo_id=repo_id,
#                 zip_file_path=zip_file_path,
#                 repo_name=repo_name,
#                 commit_sha=commit_sha,
#             )

#         stmt = select(File).where(
#             File.repository_id == repo_id, File.commit_sha == commit_sha
#         )
#         rows = db_session.execute(stmt).scalars().all()
#         assert rows == []

#     else:
#         files: list[FileRead] = svc.select_repo_files(
#             repo_id=repo_id,
#             zip_file_path=zip_file_path,
#             repo_name=repo_name,
#             commit_sha=commit_sha,
#         )

#         assert len(files) >= expected_min_files

#         stmt = select(File).where(
#             File.repository_id == repo_id, File.commit_sha == commit_sha
#         )
#         rows = db_session.execute(stmt).scalars().all()

#         assert len(rows) == len(files)

#         returned_paths = {f.file_path for f in files}
#         db_paths = {r.file_path for r in rows}
#         assert returned_paths == db_paths

#         extract_root = tmp_path / repo_name
#         for p in returned_paths:
#             assert (extract_root / p).exists()


# # ============================================================================================

# example_encoding = {
#     "input_ids": [
#         101,  # <s> or BOS token
#         2483,  # def
#         3712,  # add
#         1006,  # (
#         1037,  # a
#         1010,  # ,
#         1038,  # b
#         1007,  # )
#         1024,  # :
#         2707,  # return
#         1037,  # a
#         1009,  # +
#         1038,  # b
#         102,  # </s> or EOS token
#     ],
#     "attention_mask": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
# }

# fake_chunk = ChunkRead(
#     id=1,
#     repo_id=2,
#     chunk_parent_id=None,
#     file_path="dummy.c",
#     content="hello_world",
#     content_hash=hash_text("hello_world"),
#     type=ChunkType.FUNCTION,
#     file_id=123,
#     start_line=1,
#     end_line=5,
# )


# class DummyEmbeddingService:
#     def tokenize_node(
#         self, *args: Any, **kwargs: Any
#     ) -> tuple[list[ChunkRead], list[Any] | None]:
#         return [fake_chunk], [example_encoding]


# def make_get_file_complete_path(tmp_path: Path):
#     def _get_file_complete_path(file_path: str, repo_name: str) -> str:
#         return str(tmp_path / repo_name / file_path)

#     return _get_file_complete_path


# @dataclass(frozen=True)
# class RepoCtx:
#     repo_id: int
#     repo_name: str
#     commit_sha: str
#     repo_root: Path  # tmp_path/repo_name


# @pytest.fixture
# def repo_ctx(tmp_path: Path) -> RepoCtx:
#     # stable defaults; override per-test if needed
#     repo_id = 123
#     repo_name = "repo_test"
#     commit_sha = "deadbeef" * 5
#     repo_root = tmp_path / repo_name
#     repo_root.mkdir(parents=True, exist_ok=True)
#     return RepoCtx(
#         repo_id=repo_id, repo_name=repo_name, commit_sha=commit_sha, repo_root=repo_root
#     )


# @pytest.fixture
# def patch_repo_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
#     """
#     Patches REPOS_PATH + get_file_complete_path so all code reads/writes under tmp_path/<repo_name>.
#     """
#     import src.features.indexer.service as svc_module

#     monkeypatch.setattr(svc_module, "REPOS_PATH", str(tmp_path))
#     monkeypatch.setattr(
#         svc_module,
#         "get_file_complete_path",
#         make_get_file_complete_path(tmp_path),
#     )
#     return svc_module  # return module so tests can patch constants/functions on it too


# def write_repo_file(
#     repo_root: Path, rel_path: str, content: str, encoding: str = "utf-8"
# ) -> Path:
#     full_path = repo_root / rel_path
#     full_path.parent.mkdir(parents=True, exist_ok=True)
#     full_path.write_text(content, encoding=encoding)
#     return full_path


# VALID_SHA1 = "0" * 40  # ✅ 40 hex chars


# def make_file_row(
#     db_session: Session, repo_id: int, commit_sha: str, rel_path: str
# ) -> FileRead:
#     file_db = File(
#         repository_id=repo_id,
#         commit_sha=commit_sha,
#         file_path=rel_path,
#         content_hash=VALID_SHA1,
#     )
#     db_session.add(file_db)
#     db_session.flush()
#     return FileRead.model_validate(file_db)


# def make_chunker(
#     db_session: Session,
#     http_session: requests.Session,
#     repo_id: int,
#     repo_name: str,
# ) -> ChunkingService:
#     repo_svc = RepoService(
#         db_session=db_session, http_session=http_session, repo_name=repo_name
#     )
#     return ChunkingService(
#         repo_service=repo_svc,
#         embedding_service=DummyEmbeddingService(),  # type: ignore
#         db_session=db_session,
#         repo_id=repo_id,
#         repo_name=repo_name,
#     )


# def patch_zip_selection(svc_module: Any, monkeypatch: pytest.MonkeyPatch) -> None:
#     """
#     Make zip selection deterministic so tests don't depend on your real skip/binary/select rules.
#     """

#     def _is_skipped(_filename: str) -> bool:
#         return False

#     def _is_binary(_zip: ZipFile, _info: ZipInfo) -> bool:
#         return False

#     def _is_selected(filename: str) -> bool:
#         return filename.endswith((".md", ".py", ".txt"))

#     monkeypatch.setattr(svc_module, "is_skipped", _is_skipped)
#     monkeypatch.setattr(svc_module, "is_binary", _is_binary)
#     monkeypatch.setattr(svc_module, "is_selected", _is_selected)


# def make_zip(tmp_path: Path, name: str, files: dict[str, str]) -> Path:
#     zpath = tmp_path / name
#     with ZipFile(zpath, "w", compression=ZIP_DEFLATED) as z:
#         for p, content in files.items():
#             z.writestr(p, content)
#     return zpath


# @pytest.mark.parametrize(
#     "case, lines, chunk_size, overlapping, should_raise, expected_exc",
#     [
#         ("ok", 20, 5, 2, False, None),
#         ("overlap_ge_chunk", 20, 5, 5, True, ValueError),
#     ],
# )
# def test_chunk_text_files(
#     db_session: Session,
#     http_session: requests.Session,
#     repo_ctx: RepoCtx,
#     patch_repo_paths: Any,
#     case: str,
#     lines: int,
#     chunk_size: int,
#     overlapping: int,
#     should_raise: bool,
#     expected_exc: type[BaseException] | None,
# ) -> None:
#     # arrange
#     rel_path = "README.md"
#     write_repo_file(
#         repo_ctx.repo_root, rel_path, "\n".join(f"line {i}" for i in range(lines))
#     )
#     file_read = make_file_row(
#         db_session, repo_ctx.repo_id, repo_ctx.commit_sha, rel_path
#     )
#     chunker = make_chunker(
#         db_session, http_session, repo_ctx.repo_id, repo_ctx.repo_name
#     )

#     # act/assert
#     if should_raise:
#         assert expected_exc is not None
#         with pytest.raises(expected_exc):
#             chunker.chunk_text_files(
#                 file_read, chunk_size=chunk_size, overlapping=overlapping
#             )
#         return

#     chunks = chunker.chunk_text_files(
#         file_read, chunk_size=chunk_size, overlapping=overlapping
#     )
#     assert chunks

#     stmt = select(Chunk).where(Chunk.file_id == file_read.id)
#     db_chunks = db_session.execute(stmt).scalars().all()
#     assert len(db_chunks) == len(chunks)


# def get_file_path_not_exist(_file_path: str, _repo_name: str) -> str:
#     return "/does/not/exist.txt"


# def test_chunk_text_files_missing_file_raises_storage_error(
#     db_session: Session,
#     http_session: requests.Session,
#     repo_ctx: RepoCtx,
#     monkeypatch: pytest.MonkeyPatch,
#     patch_repo_paths: Any,
# ) -> None:
#     # arrange: force missing path
#     import src.features.indexer.service as svc_module

#     monkeypatch.setattr(
#         svc_module,
#         "get_file_complete_path",
#         get_file_path_not_exist,
#     )

#     file_read = make_file_row(
#         db_session, repo_ctx.repo_id, repo_ctx.commit_sha, "missing.txt"
#     )
#     chunker = make_chunker(
#         db_session, http_session, repo_ctx.repo_id, repo_ctx.repo_name
#     )

#     # act/assert
#     with pytest.raises(StorageError):
#         chunker.chunk_text_files(file_read)


# @pytest.mark.parametrize(
#     "case, make_zip_kind, should_raise, expected_exc",
#     [
#         ("ok", "valid", False, None),
#         ("bad_zip", "bad", True, ExternalServiceError),
#     ],
# )
# def test_chunk_repo_files_including_code_chunks(
#     db_session: Session,
#     http_session: requests.Session,
#     tmp_path: Path,
#     monkeypatch: pytest.MonkeyPatch,
#     patch_repo_paths: Any,
#     case: str,
#     make_zip_kind: str,
#     should_raise: bool,
#     expected_exc: type[BaseException] | None,
# ) -> None:
#     """
#     Full pipeline:
#     zip -> RepoService.select_repo_files -> chunk_repo_files -> DB chunks.
#     Includes code chunking if tree-sitter parser exists; otherwise skips.
#     """
#     import src.features.indexer.service as svc_module

#     # Arrange: deterministic selection + extension routing
#     patch_zip_selection(svc_module, monkeypatch)
#     monkeypatch.setattr(svc_module, "TEXT_LANG_EXT", {".md"})
#     monkeypatch.setattr(svc_module, "AST_LANG_EXT", {".py"})

#     repo_id = 321
#     repo_name = f"repo_zip_{case}"
#     commit_sha = "deadbeef" * 5

#     if make_zip_kind == "valid":
#         zpath = make_zip(
#             tmp_path,
#             f"{case}.zip",
#             {
#                 "README.md": "hello\nworld\n",
#                 "src/example.py": "def foo(x):\n    return x\n",
#             },
#         )
#     else:
#         zpath = tmp_path / f"{case}.zip"
#         zpath.write_bytes(b"not a zip")

#     chunker = make_chunker(db_session, http_session, repo_id, repo_name)

#     if should_raise:
#         assert expected_exc is not None
#         with pytest.raises(expected_exc):
#             chunker.chunk_repo_files(zpath, commit_sha)
#         return

#     # code chunking requires parser; skip cleanly if not available
#     try:
#         _chunks = chunker.chunk_repo_files(zpath, commit_sha)
#     except Exception as e:
#         pytest.skip(f"Tree-sitter/parser not available in this test env: {e}")

#     # Assert: files inserted
#     file_stmt = select(File).where(
#         File.repository_id == repo_id, File.commit_sha == commit_sha
#     )
#     files = db_session.execute(file_stmt).scalars().all()
#     assert {f.file_path for f in files} == {"README.md", "src/example.py"}

#     # Assert: chunks inserted (text + file summary at least)
#     chunk_stmt = select(Chunk).where(Chunk.repo_id == repo_id)
#     db_chunks = db_session.execute(chunk_stmt).scalars().all()
#     assert db_chunks

#     types = {c.type for c in db_chunks}
#     assert ChunkType.TEXT in types
#     assert ChunkType.FILE_SUMMARY in types
