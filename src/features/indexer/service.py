from typing import Any
import requests
from pathlib import Path
from zipfile import ZipFile, BadZipFile, LargeZipFile
from tree_sitter_language_pack import get_parser
from src.features.indexer.constants import *
from src.features.indexer.config import *
from src.features.indexer.embedder import batch_encoding, check_tokens, embed_texts, get_embedder_model, get_tokenizer  # type: ignore
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
    MAX_FUNC_SPLITTING_DEPTH,
    MIN_TAIL_LINES,
    OVERLAPPING_LINES_NUM,
)
from pgvector.sqlalchemy import Vector  # type: ignore


# ==================================================================================================
# Github:


class RepoService:
    def __init__(
        self, db_session: Session, http_session: requests.Session, repo_name: str
    ) -> None:
        self.db_session = db_session
        self.http_session = http_session
        self.repo_path = get_repo_path(repo_name=repo_name)

    def get_repo_metadata(
        self,
        owner: str,
        repo_name: str,
    ):
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
            # session.commit()
            self.db_session.refresh(repo_data)
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

    def download_repo(self, owner: str, repo_name: str):
        try:
            commits = self.http_session.get(
                f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/commits", headers=headers()
            )
            commits.raise_for_status()
            latest_commit = commits.json()[0]["sha"]

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
        zip_file_path: str,
        repo_name: str,
        commit_sha: str,
        max_size: int = 200_000,
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
        embedding_service: EmbeddingService,
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
                if tail_lines <= MIN_TAIL_LINES:
                    prev_start, _, prev_text = raw_chunks[-2]
                    new_text = prev_text + "\n" + tail_text
                    raw_chunks[-2] = (prev_start, tail_end, new_text.strip())
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
        print(f"stored_chunk -> {stored_chunk}")
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
        chunks_list: list[ChunkRead],
        lang: str | None,
        chunk_parent_id: int | None = None,
    ):
        is_fn = is_function(node, lang=lang)
        is_cls = is_class(node, lang=lang)

        if is_fn:
            text = node_text(src, node)
            # self.split_large_func_in_chunks(node=node, file=file, chunk_parent_id=chunk_parent_id, src=src)
            encodings, blocks = self.embedding_service.tokenize_node(
                text=text,
                node=node,
                file=file,
                chunk_parent_id=chunk_parent_id,
                src=src,
            )
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
            chunks_list.append(ChunkRead.model_validate(db_chunk))
            # for child in node.children:
            #     visit_node(child, src, chunks_list, file, session, lang, chunk_parent_id)
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
            chunks_list.append(ChunkRead.model_validate(db_chunk))
            for child in node.children:
                self.visit_node(
                    file=file,
                    node=child,
                    src=src,
                    chunks_list=chunks_list,
                    lang=lang,
                    chunk_parent_id=db_chunk.id,
                )
            return

        for child in node.children:
            self.visit_node(
                file=file,
                node=child,
                src=src,
                chunks_list=chunks_list,
                lang=lang,
                chunk_parent_id=chunk_parent_id,
            )

    # --------------------------------------------------------------------------------------------------
    # long function block chunking:
    # what im trying to do:
    # I check the length of the function, if long then go into children, chunk them, check the children length, if long chunk them too
    # I'm trying to keep order of statements in account
    def collect_blocks(self, node: Node, max_lines: int = MAX_LINES_NUM):
        blocks: list[Node] = []

        body = find_body(node)
        if not body:
            return blocks

        for child in body.named_children:
            if is_block(child) and (node_line_count(child) > max_lines):
                blocks.append(child)
        return blocks

    def build_parent_with_placeholders(
        self, src: bytes, node: Node, extracted_nodes: list[Node]
    ):
        body = find_body(node)
        if not body:
            return node_text(src, node)

        blocks = sorted(extracted_nodes, key=lambda n: n.start_byte)

        out: list[str] = []

        cursor = body.start_byte
        if src[cursor : cursor + 1] == b"{":
            cursor += 1

        for block in blocks:
            out.append(slice_text(src=src, a=cursor, b=block.start_byte))
            out.append(block_placeholder(src=src, node=block))
            cursor = block.end_byte

        out.append(slice_text(src=src, a=cursor, b=body.end_byte))

        function_signature = node_signature(src, node)
        return function_signature + "\n" + "".join(out)

    def func_children_chunks(
        self,
        file: FileRead,
        src: bytes,
        child_node: Node,
        parent_id: int,
        depth: int,
        max_depth: int,
        max_lines: int,
    ):
        blocks_data: list[ChunkRead] = []

        if depth + 1 <= max_depth:
            inner_blocks = self.collect_blocks(node=child_node, max_lines=max_lines)
            function_placeholder = self.build_parent_with_placeholders(
                src=src, node=child_node, extracted_nodes=inner_blocks
            )
            function_placeholder = normalize_newlines(function_placeholder)

            db_chunk = self.store_chunk_in_db(
                file_id=file.id,
                file_path=file.file_path,
                type=ChunkType.FUNCTION_INNER_BLOCK.value,
                start_line=child_node.start_point[0] + 1,
                end_line=child_node.end_point[0] + 1,
                content=function_placeholder,
                content_hash=hash_text(function_placeholder),
                chunk_parent_id=parent_id,
            )

            blocks_data.append(ChunkRead.model_validate(db_chunk))
            parent_id = db_chunk.id

            for child in inner_blocks:
                blocks_data.extend(
                    self.func_children_chunks(
                        file=file,
                        src=src,
                        child_node=child,
                        parent_id=parent_id,
                        depth=depth + 1,
                        max_depth=max_depth,
                        max_lines=max_lines,
                    )
                )
        else:
            text = node_text(src=src, node=child_node)
            text = normalize_newlines(text)

            db_chunk = self.store_chunk_in_db(
                file_id=file.id,
                file_path=file.file_path,
                type=ChunkType.FUNCTION_INNER_BLOCK.value,
                start_line=child_node.start_point[0] + 1,
                end_line=child_node.end_point[0] + 1,
                content=text,
                content_hash=hash_text(text),
                chunk_parent_id=parent_id,
            )
            blocks_data.append(ChunkRead.model_validate(db_chunk))

        return blocks_data

    def split_large_func_in_chunks(
        self,
        file: FileRead,
        src: bytes,
        node: Node,
        chunk_parent_id: int | None = None,
        depth: int = 0,
        max_depth: int = MAX_FUNC_SPLITTING_DEPTH,
        max_lines: int = MAX_LINES_NUM,
    ) -> tuple[int, list[ChunkRead]]:
        blocks_data: list[ChunkRead] = []
        body = find_body(node)

        if not body:
            raise ValueError(
                f"Failed to split function "
                f"{node.start_point[0]+1}-{node.end_point[0]+1} "
                f"in file {file.file_path}"
            )

        direct_blocks = self.collect_blocks(node=node, max_lines=max_lines)

        function_placeholder = self.build_parent_with_placeholders(
            src=src, node=node, extracted_nodes=direct_blocks
        )
        function_placeholder = normalize_newlines(function_placeholder)

        db_chunk = self.store_chunk_in_db(
            file_id=file.id,
            file_path=file.file_path,
            type=ChunkType.FUNCTION.value,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            content=function_placeholder,
            content_hash=hash_text(function_placeholder),
            chunk_parent_id=chunk_parent_id,
        )

        blocks_data.append(ChunkRead.model_validate(db_chunk))
        parent_id: int = db_chunk.id

        for block in direct_blocks:
            blocks_data.extend(
                self.func_children_chunks(
                    src=src,
                    file=file,
                    child_node=block,
                    parent_id=parent_id,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_lines=max_lines,
                )
            )

        return parent_id, blocks_data

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
        return chunk_db

    def chunk_repo_files(self, zip_file_path: str, commit_sha: str):
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
        # session.commit()
        return chunks


# ==================================================================================================
# embedding:
class EmbeddingService:
    def __init__(self, db_session: Session, chunking_service: ChunkingService) -> None:
        self.db_session = db_session
        self.chunking_service = chunking_service

    def store_embedding(self, chunk_id: int, embedding_vector: list[float]):
        embedding_data = ChunkEmbeddingCreate.model_validate(
            {"chunk_id": chunk_id, "embedding_vector": embedding_vector}
        )
        embedding_db = ChunkEmbedding(**embedding_data.model_dump())
        self.db_session.add(embedding_db)
        self.db_session.flush()
        return embedding_db

    def tokenize_node(
        self,
        node: Node,
        text: str,
        file: FileRead,
        chunk_parent_id: int | None,
        src: bytes,
    ):
        tokenizer: Any = get_tokenizer()
        enc, is_safe = check_tokens(tokenizer=tokenizer, input_text=text)

        try:
            if not is_safe:
                encoding: list[Any] = []
                parent_id, blocks = self.chunking_service.split_large_func_in_chunks(
                    file=file, chunk_parent_id=chunk_parent_id, node=node, src=src
                )
                for b in blocks:
                    new_enc = self.tokenize_node(
                        text=b.content,
                        file=file,
                        chunk_parent_id=parent_id,
                        node=node,
                        src=src,
                    )
                    encoding.extend(new_enc)
                return encoding, blocks
            else:
                return [enc]
        except ValueError:
            raise
        except Exception as e:
            raise TokenizationError(
                f"Failed to tokenize node at lines "
                f"{node.start_point[0]+1}-{node.end_point[0]+1} "
                f"in file {file.file_path}"
            ) from e

    def embed_chunks(self, chunks_list: list[ChunkRead], chunks_encoding: list[Any]):
        embedder: Any = get_embedder_model()
        tokenizer: Any = get_tokenizer()
        device = next(embedder.parameters()).device
        batched_encoding = batch_encoding(
            tokens_list=chunks_encoding, device=device, tokenizer=tokenizer
        )

        mbd = embed_texts(batched_encoding, embedder)
        mbd = tensor_to_vector(mbd)

        if len(chunks_list) != len(mbd):
            raise ValueError(f"Mismatch: {len(chunks_list)=} vs {len(mbd)=}")

        embeddings: list[ChunkEmbeddingRead] = []
        for chunk, vector in zip(chunks_list, mbd):
            embedding = self.store_embedding(chunk_id=chunk.id, embedding_vector=vector)
            embeddings.append(ChunkEmbeddingRead.model_validate(embedding))
        return embeddings
