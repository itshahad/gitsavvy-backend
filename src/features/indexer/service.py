from typing import Any
import requests
from pathlib import Path
from zipfile import ZipFile, BadZipFile, LargeZipFile
from tree_sitter_language_pack import get_parser
from src.features.indexer.constants import *
from src.features.indexer.config import *
from src.core.embedder import batch_encoding, embed_text, embed_texts  # type: ignore
from src.features.indexer.utils import *
from src.features.indexer.schemas import *
from src.features.indexer.models import *
from src.features.indexer.exceptions import *
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.exceptions import ExternalServiceError, StorageError
from sqlalchemy.exc import IntegrityError
from src.config import (
    MAX_BYTES_NUM,
    MIN_TAIL_BYTES,
    OVERLAPPING_BYTES_NUM,
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

                        path = Path(info.filename)
                        parents = path.parts[:-1]
                        parent: ModuleRead | None = None
                        for part in parents:
                            module = self.get_or_create_module(
                                repo_id=repo_id,
                                module=part,
                                parent_id=parent.id if parent else None,
                            )
                            parent = module

                        zip.extract(info.filename, extract_dir)
                        file = self.store_file_to_db(
                            repo_id,
                            commit_sha,
                            zip,
                            info,
                            parent.id if parent else None,
                        )
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
        self,
        repo_id: int,
        commit_sha: str,
        zip_file: ZipFile,
        info: ZipInfo,
        module_id: int | None,
    ):
        content_hash = hash_file_content(zip_file, info)
        data: dict[str, str | int | None] = {
            "repository_id": repo_id,
            "commit_sha": commit_sha,
            "file_path": info.filename,
            "content_hash": content_hash,
            "module_id": module_id,
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

    cashed_modules: dict[tuple[int | None, str], ModuleRead] = {}
    cached_modules_by_id: dict[int, ModuleRead] = {}

    def get_or_create_module(
        self,
        repo_id: int,
        module: str | None,
        parent_id: int | None = None,
    ):
        if module is None:
            return None

        key = (parent_id, module)

        if key not in self.cashed_modules:
            data = ModuleCreate(
                repository_id=repo_id,
                path=module,
                module_parent_id=parent_id,
            )
            module_db = Module(**data.model_dump())
            self.db_session.add(module_db)
            self.db_session.flush()
            self.db_session.refresh(module_db)
            module_read = ModuleRead.model_validate(module_db)
            self.cashed_modules[key] = ModuleRead.model_validate(module_db)
            self.cached_modules_by_id[module_read.id] = module_read

        return self.cashed_modules[key]

    def get_module_by_id(self, module_id: int | None) -> ModuleRead | None:
        if module_id is None:
            return None

        cached = self.cached_modules_by_id.get(module_id)
        if cached is not None:
            return cached

        module_db = self.db_session.get(Module, module_id)
        if module_db is None:
            return None

        module_read = ModuleRead.model_validate(module_db)
        self.cached_modules_by_id[module_id] = module_read
        return module_read


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

    def create_chunk_embedding_text(
        self,
        chunk_type: ChunkType,
        file: str,
        code: str,
        module: ModuleRead,
        lang: str | None = None,
        signature: str | None = None,
    ):
        language_line = f"\nLanguage: {lang}" if lang is not None else ""
        signature_line = f"\nSignature: {signature}" if signature is not None else ""

        content_line = ""
        if chunk_type == ChunkType.FUNCTION:
            content_line = f"\nCode:\n{code}"
        elif chunk_type == ChunkType.TEXT:
            content_line = f"\nContent:\n{code}"
        else:
            content_line = f"\nMembers:\n{code}"

        text = f"""File:{normalize_repo_path(file)}{language_line}
Type: {chunk_type.value}
Context: {module.path}{signature_line}{content_line}
"""
        return text

    # files chunking:
    def chunk_text_files(
        self,
        file: FileRead,
        module: ModuleRead,
        src: bytes,
        chunk_size: int = MAX_BYTES_NUM,
        overlapping: int = OVERLAPPING_BYTES_NUM,
        min_tail: int = MIN_TAIL_BYTES,
    ) -> list[ChunkRead]:
        try:
            if overlapping >= chunk_size:
                raise ValueError("overlapping value must be less than chunk_size")

            chunks: list[ChunkRead] = []
            step = chunk_size - overlapping

            raw_chunks: list[tuple[int, int, bytes]] = []

            n = len(src)
            for i in range(0, n, step):
                start = i
                end = min(i + chunk_size, n)

                blob = src[start:end]
                text = blob.decode("utf-8", errors="replace").strip()
                if text:
                    raw_chunks.append((start, end, blob))

            # merge small tail
            if len(raw_chunks) >= 2:
                tail_start, tail_end, tail_blob = raw_chunks[-1]
                tail_size = tail_end - tail_start
                if tail_size <= min_tail:
                    prev_start, _, prev_blob = raw_chunks[-2]
                    new_blob = prev_blob + tail_blob
                    raw_chunks[-2] = (prev_start, tail_end, new_blob)
                    raw_chunks.pop()

            for start_b, end_b, blob in raw_chunks:
                text = blob.decode("utf-8", errors="replace").strip()
                if not text:
                    continue

                content = self.create_chunk_embedding_text(
                    file=file.file_path,
                    chunk_type=ChunkType.TEXT,
                    module=module,
                    code=text,
                )

                db_chunk = self.store_chunk_in_db(
                    file_id=file.id,
                    type=ChunkType.TEXT,
                    start_byte=start_b,
                    end_byte=end_b,
                    content_text=content,
                    content_text_hash=hash_text(content),
                )
                chunks.append(ChunkRead.model_validate(db_chunk))

            return chunks

        except (PermissionError, FileNotFoundError, OSError) as e:
            msg = str(e) or "Storage read failed"
            raise StorageError(message=msg) from e

    def build_file_summary(
        self, file: FileRead, src: bytes, root: Node, lang: str, module: ModuleRead
    ):
        parts: list[Outline] = []

        for child in root.named_children:
            node = unwrap_node(child, lang=lang) or child
            if is_class(node, lang=lang):
                outline = Outline(
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                    content=node_signature(src, node),
                    type=OutlineType.CLASS,
                )

                parts.append(outline)
                continue

            if is_function(node, lang=lang):
                outline = Outline(
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                    content=node_signature(src, node),
                    type=OutlineType.Function,
                )
                parts.append(outline)
                continue

            text = node_text(src, node)

            if not text:
                continue

            outline = Outline(
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                content=text,
                type=OutlineType.STMT,
            )
            parts.append(outline)

        code = "\n".join(o.content for o in parts).strip()

        content = self.create_chunk_embedding_text(
            file=file.file_path,
            chunk_type=ChunkType.FILE_SUMMARY,
            lang=lang,
            module=module,
            code=code,
        )

        stored_chunk = self.store_chunk_in_db(
            file_id=file.id,
            type=ChunkType.FILE_SUMMARY,
            content_json=[outline_to_dict(o) for o in parts],
            content_text=content,
            content_text_hash=hash_text(content),
        )
        return stored_chunk

    def build_class_summary(
        self,
        src: bytes,
        file: FileRead,
        node: Node,
        module: ModuleRead,
        lang: str | None = None,
        chunk_parent_id: int | None = None,
    ):
        class_node = node
        parts: list[Outline] = []

        body = find_body(class_node)

        if body:
            header = slice_text(src, class_node.start_byte, body.start_byte)
            outline = Outline(
                start_byte=0,
                end_byte=0,
                content=header,
                type=OutlineType.SIGN,
            )
            parts.append(outline)

            for child in body.named_children:
                if child.type in SKIP_NODE_TYPES:
                    continue

                child_node = unwrap_node(child, lang=lang) or child
                if is_function(child_node, lang=lang):
                    outline = Outline(
                        start_byte=child_node.start_byte,
                        end_byte=child_node.end_byte,
                        content=node_signature(src, child_node),
                        type=OutlineType.Function,
                    )
                    parts.append(outline)
                    continue

                if is_class(child_node, lang=lang):
                    outline = Outline(
                        start_byte=child_node.start_byte,
                        end_byte=child_node.end_byte,
                        content=node_signature(src, child_node),
                        type=OutlineType.CLASS,
                    )
                    parts.append(outline)
                    continue

                # if this node is just a wrapper and has children, don't treat it as a class member itself let recursion handle its children
                if not child_node.is_named and child_node.children:
                    continue

                content = node_text(src, child_node).strip()
                outline = Outline(
                    start_byte=child_node.start_byte,
                    end_byte=child_node.end_byte,
                    content=content,
                    type=OutlineType.STMT,
                )
                parts.append(outline)

            code = "\n".join(o.content for o in parts).strip()

            content = self.create_chunk_embedding_text(
                file=file.file_path,
                chunk_type=ChunkType.CLASS_SUMMARY,
                lang=lang,
                signature=header,
                module=module,
                code=code,
            )

            stored_chunk = self.store_chunk_in_db(
                file_id=file.id,
                type=ChunkType.CLASS_SUMMARY,
                content_json=[outline_to_dict(o) for o in parts],
                content_text=content,
                content_text_hash=hash_text(content),
                start_byte=class_node.start_byte,
                end_byte=class_node.end_byte,
                chunk_parent_id=chunk_parent_id,
            )
            return stored_chunk

    def build_function_chunk(
        self,
        src: bytes,
        file: FileRead,
        node: Node,
        module: ModuleRead,
        lang: str | None = None,
        chunk_parent_id: int | None = None,
    ):
        body = find_body(node)
        fun = node_text(src, node)

        outline = Outline(
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            content=node_signature(src, node),
            type=OutlineType.Function,
        )

        content = self.create_chunk_embedding_text(
            file=file.file_path,
            chunk_type=ChunkType.FUNCTION,
            lang=lang,
            module=module,
            code=fun,
        )
        if body:
            header = slice_text(src, node.start_byte, body.start_byte)
            content = self.create_chunk_embedding_text(
                file=file.file_path,
                chunk_type=ChunkType.FUNCTION,
                lang=lang,
                module=module,
                code=fun,
                signature=header,
            )

        db_chunk = self.store_chunk_in_db(
            file_id=file.id,
            type=ChunkType.FUNCTION,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            content_text=content,
            content_text_hash=hash_text(content),
            content_json=[outline_to_dict(outline)],
            chunk_parent_id=chunk_parent_id,
        )
        return db_chunk

    def visit_node(
        self,
        file: FileRead,
        node: Node,
        src: bytes,
        chunks: list[ChunkRead],
        module: ModuleRead,
        lang: str | None,
        chunk_parent_id: int | None = None,
    ):
        is_fn = is_function(node, lang=lang)
        is_cls = is_class(node, lang=lang)

        if is_fn:
            stored_chunk = self.build_function_chunk(
                src=src,
                node=node,
                file=file,
                lang=lang,
                module=module,
                chunk_parent_id=chunk_parent_id,
            )
            chunks.append(ChunkRead.model_validate(stored_chunk))
            return
        elif is_cls:
            stored_chunk = self.build_class_summary(
                src=src,
                node=node,
                file=file,
                lang=lang,
                module=module,
                chunk_parent_id=chunk_parent_id,
            )
            if stored_chunk is not None:
                chunks.append(ChunkRead.model_validate(stored_chunk))
                for child in node.children:
                    self.visit_node(
                        file=file,
                        node=child,
                        src=src,
                        chunks=chunks,
                        lang=lang,
                        module=module,
                        chunk_parent_id=stored_chunk.id,
                    )
                return
        for child in node.children:
            self.visit_node(
                file=file,
                node=child,
                src=src,
                chunks=chunks,
                lang=lang,
                module=module,
                chunk_parent_id=chunk_parent_id,
            )

    # --------------------------------------------------------------------------------------------------

    def chunk_code_files(
        self, file_path: str, src: bytes, file: FileRead, module: ModuleRead
    ) -> list[ChunkRead]:
        chunks: list[ChunkRead] = []

        file_ext = ext(file_path)
        lang = lang_from_ext(file_ext)

        if lang is None:
            return []

        parser = get_parser(language_name=lang)

        tree = parser.parse(src)
        root = tree.root_node

        db_file_chunk = self.build_file_summary(file, src, root, lang, module=module)
        chunks.append(ChunkRead.model_validate(db_file_chunk))
        self.visit_node(
            file=file,
            node=root,
            src=src,
            chunks=chunks,
            lang=lang,
            chunk_parent_id=db_file_chunk.id,
            module=module,
        )
        return chunks

    # --------------------------------------------------------------------------------------------------

    def store_chunk_in_db(
        self,
        file_id: int,
        type: ChunkType,
        content_text: str,
        content_text_hash: str,
        content_json: list[dict[str, int | str]] | None = None,
        start_byte: int | None = None,
        end_byte: int | None = None,
        chunk_parent_id: int | None = None,
    ):

        chunk_data = ChunkCreate(
            file_id=file_id,
            repo_id=self.repo_id,
            chunk_parent_id=chunk_parent_id,
            start_byte=start_byte,
            end_byte=end_byte,
            type=type,
            content_text=content_text,
            content_json=content_json,
            content_text_hash=content_text_hash,
        )
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
            module = self.repo_service.get_module_by_id(module_id=file.module_id)
            if module is None:
                raise ValueError(f"No module found for this file {file.file_path}")

            file_path = get_file_complete_path(file.file_path, self.repo_name)
            file_bytes = Path(file_path).read_bytes()

            e = ext(file.file_path)

            if e in AST_LANG_EXT:
                print(f"AST_LANG_EXT -> {file.file_path}")
                chunks.extend(
                    self.chunk_code_files(
                        file=file, file_path=file_path, src=file_bytes, module=module
                    )
                )
            elif e in TEXT_LANG_EXT:
                print(f"TEXT_LANG_EXT -> {file.file_path}")
                chunks.extend(
                    self.chunk_text_files(file, src=file_bytes, module=module)
                )
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
        chunking_service: "ChunkingService | None" = None,
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
        is_commit: bool = False,
    ):
        device = next(self.embedder.parameters()).device
        embeddings: list[ChunkEmbeddingRead] = []
        for chunk in chunks:
            vec, _meta = embed_text(
                text=chunk.content_text,
                tokenizer=self.tokenizer,
                model=self.embedder,
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

    def embed_text(self, text: str):
        device = next(self.embedder.parameters()).device
        vec, _meta = embed_text(
            text=text,
            tokenizer=self.tokenizer,
            model=self.embedder,
            batch_encoding=batch_encoding,
            embed_texts=embed_texts,
            device=device,
        )
        return vec, _meta
