from pathlib import Path
from typing import Any, Generator
from sqlalchemy.orm import Session
from sqlalchemy import case, or_, select
from sqlalchemy.exc import SQLAlchemyError

from src.exceptions import DatabaseError
from src.features.documentation_generator.exceptions import (
    FileNotFound,
    ModuleNotFound,
    RepoNotFound,
)
from src.core.llm import generate_llm_response  # type: ignore

from src.features.documentation_generator.models import Documentation
from src.features.documentation_generator.schemas import (
    ChunkType,
    DocCreate,
    DocModel,
)
from src.features.documentation_generator.schemas import DocRead
from src.features.documentation_generator.utils import (
    extract_code,
    extract_signature,
    parse_yaml_front_matter,
)

from src.features.indexer.schemas import ChunkRead
from src.features.indexer.utils import get_file_complete_path, normalize_repo_path
from src.features.repositories.constants import AST_LANG_EXT
from src.features.indexer.models import Chunk
from src.features.repositories.models import File, Module, Repository
from src.features.repositories.schemas import FileRead, ModuleRead, RepoRead
from src.models_loader import OutlineType


class DocGenerateService:
    def __init__(
        self,
        session: Session,
        repo_id: int,
        repo_name: str,
        tokenizer: Any,
        model: Any,
        start_from_module_id: int | None = None,
        start_from_file_id: int | None = None,
        start_from_chunk_id: int | None = None,
    ) -> None:
        self.session = session
        self.repo_id = repo_id
        self.repo_name = repo_name
        self.tokenizer = tokenizer
        self.model = model
        # self.llm_service = llm_service
        self.start_from_module_id = start_from_module_id
        self.start_from_file_id = start_from_file_id
        self.start_from_chunk_id = start_from_chunk_id

    def get_modules(self, batch_size: int = 20) -> Generator[Module, None, None]:
        filters = [Module.repository_id == self.repo_id]
        if self.start_from_module_id is not None:
            filters.append(Module.id >= self.start_from_module_id)
        q = (
            self.session.query(Module)
            .filter(*filters)
            .order_by(Module.id)
            .execution_options(stream_results=True)
            .yield_per(batch_size)
        )

        iterator = iter(q)
        first = next(iterator, None)
        if not first:
            raise ValueError("No module found")

        yield first
        yield from iterator

    def get_files(
        self, module: ModuleRead, batch_size: int = 20
    ) -> Generator[File, None, None]:
        ext_filter = [File.file_path.endswith(ext) for ext in AST_LANG_EXT]

        filters = [
            File.repository_id == self.repo_id,
            File.module_id == module.id,
            or_(*ext_filter),
        ]

        if self.start_from_file_id is not None:
            filters.append(File.id >= self.start_from_file_id)

        print(f"module id: {module.id}")

        q = (
            self.session.query(File)
            .filter(*filters)
            .order_by(File.id)
            .execution_options(stream_results=True)
            .yield_per(batch_size)
        )

        yield from q

    def get_file_chunks(
        self,
        file: FileRead,
        type: ChunkType | None = None,
        chunk_parent_id: int | None = None,
        batch_size: int = 20,
    ) -> Generator[Chunk, None, None]:
        filters = [Chunk.file_id == file.id]

        if type is not None:
            filters.append(Chunk.type == type)

        if chunk_parent_id is not None:
            filters.append(Chunk.chunk_parent_id == chunk_parent_id)

        if self.start_from_chunk_id is not None:
            filters.append(Chunk.id >= self.start_from_chunk_id)

        q = (
            self.session.query(Chunk)
            .filter(*filters)
            .order_by(Chunk.id)
            .execution_options(stream_results=True)
            .yield_per(batch_size)
        )

        yield from q

    # ==========================================================================

    def generate_docs(self):
        from tqdm import tqdm

        files_doc: dict[int, DocRead] = {}
        modules = list(self.get_modules())
        for module in tqdm(modules, desc=f"Modules"):
            module_read = ModuleRead.model_validate(module)

            files = list(self.get_files(module=module_read))
            for file in tqdm(
                files, desc=f"Files in module {module_read.id}", leave=False
            ):
                file_read = FileRead.model_validate(file)
                file_path = get_file_complete_path(file.file_path, self.repo_name)
                file_bytes = Path(file_path).read_bytes()

                file_chunk = next(
                    self.get_file_chunks(file=file_read, type=ChunkType.FILE_SUMMARY),
                    None,
                )

                if file_chunk is None:
                    continue

                children_docs = self.generate_children_chunks_docs(
                    file=file_read, src=file_bytes, chunk_parent_id=file_chunk.id
                )

                file_chunk_doc = self.generate_chunk_docs(
                    chunk=file_chunk,
                    file=file_read,
                    src=file_bytes,
                    children_docs=children_docs,
                )

                files_doc[file_chunk.id] = file_chunk_doc
            self.session.commit()
        return files_doc

    def generate_children_chunks_docs(
        self, file: FileRead, src: bytes, chunk_parent_id: int
    ):
        docs: dict[int, DocRead] = {}
        for chunk in self.get_file_chunks(file=file, chunk_parent_id=chunk_parent_id):

            children_docs = self.generate_children_chunks_docs(
                file=file, src=src, chunk_parent_id=chunk.id
            )

            docs[chunk.start_byte] = self.generate_chunk_docs(
                src=src,
                chunk=chunk,
                children_docs=children_docs,
                file=file,
            )
        return docs

    def generate_chunk_docs(
        self,
        src: bytes,
        chunk: Chunk,
        file: FileRead,
        children_docs: dict[int, DocRead],
    ):
        content = chunk.content_json

        text = self.build_text_from_ranges(
            src=src, ranges=content, children_docs=children_docs
        )

        doc = generate_llm_response(
            file_path=normalize_repo_path(file.file_path),
            content=text,
            tokenizer=self.tokenizer,
            model=self.model,
        )

        short_summary, detailed_documentation = parse_yaml_front_matter(doc)

        stored_doc = self.store_doc_artifact(
            chunk=chunk,
            detailed_doc=detailed_documentation,
            short_summary=short_summary,
        )

        return stored_doc

    def build_text_from_ranges(
        self,
        src: bytes,
        ranges: list[dict[str, Any]],
        children_docs: dict[int, DocRead],
    ) -> str:
        parts: list[str] = []

        if len(ranges) == 1 and ranges[0].get("type") == OutlineType.Function.value:
            start = int(ranges[0]["start_byte"])
            end = int(ranges[0]["end_byte"])
            return src[start:end].decode("utf-8", errors="replace")

        for r in ranges:
            content = r["content"]
            start_byte = r["start_byte"]
            type = r["type"]
            text = ""
            if type == OutlineType.SIGN.value:
                text = f"ENTITY: {content}\n\nMEMBERS:\n"
            elif type == OutlineType.STMT.value:
                text = content
            elif type == OutlineType.Function.value or type == OutlineType.CLASS.value:
                child_doc = children_docs.get(start_byte)
                text = (
                    f"{content}\nSUMMARY: {child_doc.short_summary}"
                    if child_doc
                    else content
                )
            parts.append(text)

        return "\n".join(parts)

    def store_doc_artifact(self, chunk: Chunk, short_summary: str, detailed_doc: str):
        data: dict[str, str | int] = {
            "chunk_id": chunk.id,
            "short_summary": short_summary,
            "detailed_doc": detailed_doc,
        }

        doc_data = DocCreate.model_validate(data)
        doc_db = Documentation(**doc_data.model_dump())
        self.session.add(doc_db)
        self.session.flush()
        self.session.refresh(doc_db)
        return DocRead.model_validate(doc_db)


class DocService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_repo(self, repo_id: int):
        repo = self.db.get(Repository, repo_id)
        if repo is None:
            raise RepoNotFound(repo_id=repo_id)
        return RepoRead.model_validate(repo)

    def get_module(self, module_id: int):
        module = self.db.get(Module, module_id)
        if module is None:
            raise ModuleNotFound(module_id=module_id)
        return ModuleRead.model_validate(module)

    def get_file(self, file_id: int):
        file = self.db.get(File, file_id)
        if file is None:
            raise FileNotFound(file_id=file_id)
        return FileRead.model_validate(file)

    def get_modules(self, repo_id: int, limit: int = 20, cursor: int | None = None):
        try:
            self.get_repo(repo_id=repo_id)
            filters = [Module.repository_id == repo_id]
            if cursor is not None:
                filters.append(Module.id > cursor)
            stmt = select(Module).where(*filters).order_by(Module.id).limit(limit + 1)

            modules = self.db.execute(stmt).scalars().all()

            has_more = len(modules) > limit
            next_cursor = None

            if has_more:
                next_cursor = modules[-1].id
                modules = modules[:limit]

            return (
                [ModuleRead.model_validate(module) for module in modules],
                next_cursor,
            )
        except SQLAlchemyError as e:
            raise DatabaseError from e

    def get_files(self, module_id: int, limit: int = 20, cursor: int | None = None):
        try:
            self.get_module(module_id=module_id)
            filters = [File.module_id == module_id]
            if cursor is not None:
                filters.append(File.id > cursor)
            stmt = select(File).where(*filters).order_by(File.id).limit(limit + 1)

            files = self.db.execute(stmt).scalars().all()

            has_more = len(files) > limit
            next_cursor = None

            if has_more:
                next_cursor = files[-1].id
                files = files[:limit]

            return ([FileRead.model_validate(file) for file in files], next_cursor)
        except SQLAlchemyError as e:
            raise DatabaseError from e

    def get_chunk_documentation(
        self,
        file_id: int,
        limit: int = 20,
        cursor: int | None = None,
    ):
        try:
            self.get_file(file_id=file_id)
            order_case = case(
                (Chunk.type == ChunkType.FILE_SUMMARY, 0),
                (Chunk.type == ChunkType.CLASS_SUMMARY, 1),
                (Chunk.type == ChunkType.FUNCTION, 2),
                else_=99,
            )
            filters = [Chunk.file_id == file_id]
            if cursor is not None:
                filters.append(Chunk.id > cursor)
            stmt = (
                select(Chunk, Documentation)
                .join(Documentation, Documentation.chunk_id == Chunk.id)
                .where(*filters)
                .order_by(order_case, Chunk.start_byte)
                .limit(limit + 1)
            )

            rows = self.db.execute(stmt).all()

            has_more = len(rows) > limit
            next_cursor = None

            if has_more:
                next_cursor = rows[-1][0].id  # each row is (chunk, documentation)
                rows = rows[:limit]

            docs: list[DocModel] = []
            for chunk, doc in rows:
                chunk_model = ChunkRead.model_validate(chunk)
                doc_model = DocRead.model_validate(doc)
                code = extract_code(chunk_model.content_text)
                signature = extract_signature(chunk_model.content_text)
                doc_chunk = DocModel(
                    chunk_id=chunk_model.id,
                    doc_id=doc_model.id,
                    code=code,
                    docs=doc_model.detailed_doc,
                    type=chunk_model.type,
                    signature=signature if signature != "" else None,
                    chunk_parent_id=chunk_model.chunk_parent_id,
                    start_byte=chunk_model.start_byte,
                    end_byte=chunk_model.end_byte,
                )
                docs.append(doc_chunk)

            return (docs, next_cursor)

        except SQLAlchemyError as e:
            raise DatabaseError from e
