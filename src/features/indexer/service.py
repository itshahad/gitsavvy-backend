from typing import Any
import requests
from pathlib import Path
from zipfile import ZipFile, BadZipFile, LargeZipFile
from tree_sitter_language_pack import get_parser
from src.features.indexer.constants import *
from src.features.indexer.config import *
from src.features.indexer.embedder import batch_encoding, embed_text, embed_texts  # type: ignore
from src.features.indexer.utils import *
from src.features.indexer.schemas import *
from src.features.indexer.models import *
from src.features.indexer.exceptions import *
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.exceptions import ExternalServiceError, StorageError
from sqlalchemy.exc import IntegrityError
from src.config import (
    MAX_LINES_NUM,
    MIN_TAIL_LINES,
    OVERLAPPING_LINES_NUM,
)


# ==================================================================================================
# Github:
class RepoService:
    def __init__(
        self, db_session: Session, http_session: requests.Session, repo_name: str
    ) -> None:
        self.db_session = db_session
        self.http_session = http_session
        self.repo_path = get_repo_path(repo_name=repo_name)

    def get_repo_metadata(self, owner: str, repo_name: str, is_commit: bool = False):
        try:
            r = self.http_session.get(
                f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}", headers=headers()
            )
            r.raise_for_status()
            repo_metadata = RepoCreate.model_validate(r.json())
            repo_data = Repository(
                **repo_metadata.model_dump(
                    exclude={"topics", "url", "avatar_url", "language"}
                ),
                url=str(repo_metadata.url),
                avatar_url=(
                    str(repo_metadata.avatar_url) if repo_metadata.avatar_url else None
                ),
            )

            self.db_session.add(repo_data)
            self.db_session.flush()  # to get an id
            self.db_session.add_all(
                [
                    RepositoryTopic(repository_id=repo_data.id, topic=t)
                    for t in repo_metadata.topics
                ]
            )
            self.db_session.refresh(repo_data)

            if is_commit:
                self.db_session.commit()

            return RepoRead.model_validate(repo_data)

        except IntegrityError as e:
            self.db_session.rollback()
            stmt = select(Repository).where(
                Repository.owner == owner, Repository.name == repo_name
            )
            repo_from_db = get_item_from_db(self.db_session, stmt)
            if repo_from_db is None:
                raise
            return RepoRead.model_validate(repo_from_db)

        except Exception as e:
            raise_request_exception(e=e, owner=owner, repo_name=repo_name)

    def download_repo(self, owner: str, repo_name: str) -> tuple[str, str]:
        try:
            commits = self.http_session.get(
                f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/commits", headers=headers()
            )
            commits.raise_for_status()
            latest_commit: str = commits.json()[0]["sha"]

            self.repo_path.parent.mkdir(parents=True, exist_ok=True)
            r = self.http_session.get(
                f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/zipball/{latest_commit}",
                headers=headers(),
            )
            r.raise_for_status()
            with open(self.repo_path, mode="wb") as file:
                file.write(r.content)

            return str(self.repo_path), latest_commit
        except (PermissionError, FileNotFoundError, OSError) as e:
            msg = str(e) or "Storage write failed"
            raise StorageError(message=msg) from e
        except Exception as e:
            raise_request_exception(e=e, owner=owner, repo_name=repo_name)

    # file selection: -----------------------------------------------------------------------------

    def select_repo_files(
        self,
        repo_id: int,
        zip_file_path: Path,
        repo_name: str,
        commit_sha: str,
        max_size: int = 200_000,
        is_commit: bool = False,
    ):  # 200KB per file
        try:
            selected_files: list[FileRead] = []
            extract_dir = Path(f"{REPOS_PATH}/{repo_name}")

            with ZipFile(zip_file_path, "r") as zip:
                for info in zip.infolist():
                    if info.is_dir() or info.file_size > max_size:
                        continue

                    if (
                        not is_skipped(info.filename)
                        and not is_binary(zip, info)
                        and is_selected(info.filename)
                    ):
                        zip.extract(info.filename, extract_dir)
                        file = self.store_file_to_db(repo_id, commit_sha, zip, info)
                        selected_files.append(file)

                if is_commit:
                    self.db_session.commit()
            return selected_files

        except (BadZipFile, LargeZipFile) as e:
            raise ExternalServiceError(
                service="ZIP", message="invalid zip archive"
            ) from e

        except (PermissionError, FileNotFoundError, OSError) as e:
            msg = str(e) or "Storage read failed"
            raise StorageError(message=msg) from e

    def store_file_to_db(
        self, repo_id: int, commit_sha: str, zip_file: ZipFile, info: ZipInfo
    ):
        content_hash = hash_file_content(zip_file, info)
        data: dict[str, str | int] = {
            "repository_id": repo_id,
            "commit_sha": commit_sha,
            "file_path": info.filename,
            "content_hash": content_hash,
        }
        try:
            file_data = FileCreate.model_validate(data)
            file_db = File(**file_data.model_dump())
            self.db_session.add(file_db)
            self.db_session.flush()
            self.db_session.refresh(file_db)
            return FileRead.model_validate(file_db)
        except IntegrityError:
            self.db_session.rollback()
            stmt = select(File).where(
                File.repository_id == data["repository_id"],
                File.commit_sha == data["commit_sha"],
                File.file_path == data["file_path"],
            )
            file_from_db = get_item_from_db(self.db_session, stmt)
            if file_from_db is None:
                raise
            return FileRead.model_validate(file_from_db)


# ==================================================================================================


class ChunkingService:
    def __init__(
        self,
        repo_service: RepoService,
        embedding_service: "EmbeddingService",
        db_session: Session,
        repo_id: int,
        repo_name: str,
    ) -> None:
        self.repo_service = repo_service
        self.db_session = db_session
        self.repo_id = repo_id
        self.repo_name = repo_name
        self.embedding_service = embedding_service

    # files chunking:
    def chunk_text_files(
        self,
        file: FileRead,
        chunk_size: int = MAX_LINES_NUM,
        overlapping: int = OVERLAPPING_LINES_NUM,
        min_tail_lines: int = MIN_TAIL_LINES,
    ):
        try:
            if overlapping >= chunk_size:
                raise ValueError("overlapping value must be less than chunk_size")

            chunks: list[ChunkRead] = []
            file_path = get_file_complete_path(file.file_path, self.repo_name)

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            step = chunk_size - overlapping

            raw_chunks: list[tuple[int, int, str]] = []

            for i in range(0, len(lines), step):
                start = i
                end = min(i + chunk_size, len(lines))
                chunk = lines[i:end]
                text = "\n".join(chunk).strip()
                if text:
                    raw_chunks.append((start, end, text))

            if len(raw_chunks) >= 2:
                tail_start, tail_end, tail_text = raw_chunks[-1]
                tail_lines = tail_end - tail_start
                if tail_lines <= min_tail_lines:
                    prev_start, _, prev_text = raw_chunks[-2]
                    new_text = prev_text + "\n" + tail_text
                    raw_chunks[-2] = (
                        prev_start,
                        tail_end,
                        new_text.strip(),
                    )
                    raw_chunks.pop()

            for start_line, end_line, text in raw_chunks:
                db_chunk = self.store_chunk_in_db(
                    file_id=file.id,
                    file_path=file.file_path,
                    type=ChunkType.TEXT.value,
                    start_line=start_line,
                    end_line=end_line,
                    content=text,
                    content_hash=hash_text(text),
                )
                chunks.append(ChunkRead.model_validate(db_chunk))
            return chunks
        except (PermissionError, FileNotFoundError, OSError) as e:
            msg = str(e) or "Storage read failed"
            raise StorageError(message=msg) from e

    # code files chunking ----------------------------------------------------------------
    def build_file_summary(self, file: FileRead, src: bytes, root: Node, lang: str):
        parts: list[str] = []

        classes_and_methods: list[str] = []
        for child in root.named_children:
            if is_class(child, lang=lang) or is_function(child, lang=lang):
                classes_and_methods.append(node_signature(src, child))
                continue

            wrapped_node = unwrap_node(child, lang=lang)
            if wrapped_node:
                classes_and_methods.append(node_signature(src, wrapped_node))
                continue

            text = node_text(src, child)
            if not text:
                continue
            parts.append(text)

        if classes_and_methods:
            parts.append(
                "\nClasses/Methods in file:\n"
                + "\n".join(f"{item}" for item in classes_and_methods).strip()
            )

        text = "\n".join(parts).strip()

        stored_chunk = self.store_chunk_in_db(
            file_id=file.id,
            file_path=file.file_path,
            type=ChunkType.FILE_SUMMARY.value,
            content=text,
            content_hash=hash_text(text),
        )
        return stored_chunk

    def build_class_summary(self, src: bytes, node: Node, lang: str | None):
        parts: list[str] = []

        body = find_body(node)

        header = (
            slice_text(src, node.start_byte, body.start_byte)
            if body
            else node_text(src, node)
        )
        parts.append(header.strip())

        simple_contents: list[str] = []
        classes_and_methods: list[str] = []

        if body:
            for child in body.named_children:
                if child.type in SKIP_NODE_TYPES:
                    continue

                if is_function(child, lang=lang) or is_class(child, lang=lang):
                    classes_and_methods.append(node_signature(src, child))
                    continue

                wrapped_function = unwrap_node(child, lang=lang)
                if wrapped_function:
                    classes_and_methods.append(node_signature(src, wrapped_function))
                    continue

                # if this node is just a wrapper and has children, don't treat it as a class member itself let recursion handle its children
                if not child.is_named and child.children:
                    continue

                content = node_text(src, child).strip()
                simple_contents.append(content)
        if simple_contents:
            parts.append(
                "\nMembers/Comments:\n" + "\n".join(f"{m}" for m in simple_contents)
            )
        if classes_and_methods:
            parts.append(
                "\nMethods:\n" + "\n".join(f"{m}" for m in classes_and_methods)
            )
        return "\n".join(parts).strip()

    def visit_node(
        self,
        file: FileRead,
        node: Node,
        src: bytes,
        chunks: list[ChunkRead],
        lang: str | None,
        chunk_parent_id: int | None = None,
    ):
        is_fn = is_function(node, lang=lang)
        is_cls = is_class(node, lang=lang)

        if is_fn:
            text = node_text(src, node)
            db_chunk = self.store_chunk_in_db(
                file_id=file.id,
                file_path=file.file_path,
                type=ChunkType.FUNCTION.value,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                content=text,
                content_hash=hash_text(text),
                chunk_parent_id=chunk_parent_id,
            )
            chunks.append(ChunkRead.model_validate(db_chunk))
            return
        elif is_cls:
            text = self.build_class_summary(src, node, lang)
            db_chunk = self.store_chunk_in_db(
                file_id=file.id,
                file_path=file.file_path,
                type=ChunkType.CLASS_SUMMARY.value,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                content=text,
                content_hash=hash_text(text),
                chunk_parent_id=chunk_parent_id,
            )
            chunks.append(ChunkRead.model_validate(db_chunk))
            for child in node.children:
                self.visit_node(
                    file=file,
                    node=child,
                    src=src,
                    chunks=chunks,
                    lang=lang,
                    chunk_parent_id=db_chunk.id,
                )
            return
        for child in node.children:
            self.visit_node(
                file=file,
                node=child,
                src=src,
                chunks=chunks,
                lang=lang,
                chunk_parent_id=chunk_parent_id,
            )

    # --------------------------------------------------------------------------------------------------

    def chunk_code_files(self, file: FileRead) -> list[ChunkRead]:
        chunks: list[ChunkRead] = []

        file_path = get_file_complete_path(file.file_path, self.repo_name)
        file_ext = ext(file_path)
        lang = lang_from_ext(file_ext)

        if lang is None:
            return []

        file_bytes = Path(file_path).read_bytes()
        parser = get_parser(language_name=lang)

        tree = parser.parse(file_bytes)
        root = tree.root_node

        db_file_chunk = self.build_file_summary(file, file_bytes, root, lang)
        chunks.append(ChunkRead.model_validate(db_file_chunk))
        self.visit_node(
            file,
            root,
            file_bytes,
            chunks,
            lang,
            chunk_parent_id=db_file_chunk.id,
        )

        return chunks

    # --------------------------------------------------------------------------------------------------

    def store_chunk_in_db(
        self,
        file_id: int,
        file_path: str,
        type: str,
        content: str,
        content_hash: str,
        start_line: int | None = None,
        end_line: int | None = None,
        chunk_parent_id: int | None = None,
    ):
        data: dict[str, int | str] = {
            "repo_id": self.repo_id,
            "file_id": file_id,
            "file_path": file_path,
            "type": type,
            "content": content,
            "content_hash": content_hash,
        }

        if start_line is not None and end_line is not None:
            data["start_line"] = start_line
            data["end_line"] = end_line

        if chunk_parent_id is not None:
            data["chunk_parent_id"] = chunk_parent_id

        chunk_data = ChunkCreate.model_validate(data)
        chunk_db = Chunk(**chunk_data.model_dump())
        self.db_session.add(chunk_db)
        self.db_session.flush()
        self.db_session.refresh(chunk_db)
        return chunk_db

    def chunk_repo_files(
        self, zip_file_path: Path, commit_sha: str, is_commit: bool = False
    ):
        chunks: list[ChunkRead] = []
        selected_files = self.repo_service.select_repo_files(
            self.repo_id, zip_file_path, self.repo_name, commit_sha
        )

        for file in selected_files:
            e = ext(file.file_path)

            if e in AST_LANG_EXT:
                print(f"AST_LANG_EXT -> {file.file_path}")
                chunks.extend(self.chunk_code_files(file))
            elif e in TEXT_LANG_EXT:
                print(f"TEXT_LANG_EXT -> {file.file_path}")
                chunks.extend(self.chunk_text_files(file))
        if is_commit:
            self.db_session.commit()
        return chunks


# ==================================================================================================
# embedding:
class EmbeddingService:
    def __init__(
        self,
        db_session: Session,
        embedder: Any,
        tokenizer: Any,
        chunking_service: "ChunkingService | None",
    ) -> None:
        self.db_session = db_session
        self.chunking_service = chunking_service
        self.embedder = embedder
        self.tokenizer = tokenizer

    def store_embedding(self, chunk_id: int, embedding_vector: list[float]):
        embedding_data = ChunkEmbeddingCreate.model_validate(
            {"chunk_id": chunk_id, "embedding_vector": embedding_vector}
        )
        embedding_db = ChunkEmbedding(**embedding_data.model_dump())
        self.db_session.add(embedding_db)
        self.db_session.flush()
        self.db_session.refresh(embedding_db)
        return embedding_db

    def embed_chunks(
        self,
        chunks: list[ChunkRead],
        tokenizer: Any,
        embedder: Any,
        is_commit: bool = False,
    ):
        device = next(embedder.parameters()).device
        embeddings: list[ChunkEmbeddingRead] = []
        for chunk in chunks:
            vec, _meta = embed_text(
                text=chunk.content,
                tokenizer=tokenizer,
                model=embedder,
                batch_encoding=batch_encoding,
                embed_texts=embed_texts,
                device=device,
            )

            print(_meta)
            embedding_db = self.store_embedding(chunk_id=chunk.id, embedding_vector=vec)
            embeddings.append(ChunkEmbeddingRead.model_validate(embedding_db))

        if is_commit:
            self.db_session.commit()
        return embeddings
