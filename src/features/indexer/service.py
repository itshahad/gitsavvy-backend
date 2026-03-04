from typing import Any
from pathlib import Path
from sqlalchemy import select
from tree_sitter_language_pack import get_parser
from src.features.indexer.constants import *
from src.features.indexer.config import *
from src.core.embedder import batch_encoding, embed_text, embed_texts  # type: ignore
from src.features.indexer.utils import *
from src.features.indexer.schemas import *
from src.features.indexer.models import *
from src.features.indexer.exceptions import *
from sqlalchemy.orm import Session
from src.exceptions import StorageError
from src.config import (
    MAX_BYTES_NUM,
    MIN_TAIL_BYTES,
    OVERLAPPING_BYTES_NUM,
)
from src.features.repositories.constants import AST_LANG_EXT, TEXT_LANG_EXT
from src.features.repositories.models import Module, File
from src.features.repositories.schemas import FileRead, ModuleRead
from src.features.repositories.utils import ext


# ==================================================================================================
# Github:


class ChunkingService:
    def __init__(
        self,
        embedding_service: "EmbeddingService",
        db_session: Session,
        repo_id: int,
        repo_name: str,
    ) -> None:
        self.db_session = db_session
        self.repo_id = repo_id
        self.repo_name = repo_name
        self.embedding_service = embedding_service

    cached_modules_by_id: dict[int, ModuleRead] = {}

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

    def get_selected_files(self, repo_id: int):
        stmt = select(File).where(File.repository_id == repo_id).order_by(File.id)
        files = self.db_session.execute(stmt).scalars().all()

        return [FileRead.model_validate(file) for file in files]

    def chunk_repo_files(
        self,
        selected_files: list[FileRead],
        is_commit: bool = False,
    ):
        chunks: list[ChunkRead] = []

        for file in selected_files:
            module = self.get_module_by_id(module_id=file.module_id)
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
