from ast import Module
from typing import Any, Generator
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.features.documentation_generator.llm import create_docs_generation_prompt, create_model_input, decode_generated_text, generate_text  # type: ignore

from src.features.documentation_generator.models import Documentation
from src.features.documentation_generator.schemas import DocCreate
from src.features.documentation_generator.tasks import DocRead
from src.features.documentation_generator.utils import parse_yaml_front_matter
from src.features.indexer.models import Chunk, Module, ChunkType, File
from src.features.indexer.constants import AST_LANG_EXT
from src.features.indexer.router import FileRead, Path, get_file_complete_path
from src.features.indexer.schemas import ModuleRead
from src.features.indexer.service import normalize_repo_path
from src.models_loader import OutlineType


class DocGenerateService:
    def __init__(
        self, session: Session, repo_id: int, repo_name: str, llm_service: "LlmService"
    ) -> None:
        self.session = session
        self.repo_id = repo_id
        self.repo_name = repo_name
        self.llm_service = llm_service

    def get_modules(self, batch_size: int = 20) -> Generator[Module, None, None]:
        q = (
            self.session.query(Module)
            .filter(
                Module.repository_id == self.repo_id,
            )
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
        q = (
            self.session.query(File)
            .filter(
                File.repository_id == self.repo_id,
                File.module_id == module.id,
                or_(*ext_filter),
            )
            .order_by(File.id)
            .execution_options(stream_results=True)
            .yield_per(batch_size)
        )

        iterator = iter(q)
        first = next(iterator, None)
        if not first:
            raise ValueError("No file found")

        yield first
        yield from iterator

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

        doc = self.llm_service.generate_llm_response(
            file_path=normalize_repo_path(file.file_path), content=text
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


class LlmService:
    def __init__(self, session: Session, llm_model: Any, tokenizer: Any) -> None:
        self.session = session
        self.llm_model = llm_model
        self.tokenizer = tokenizer

    def generate_llm_response(self, file_path: str, content: str):
        prompt = create_docs_generation_prompt(file_path=file_path, content=content)

        input = create_model_input(
            messages=prompt, tokenizer=self.tokenizer, model=self.llm_model
        )

        gen_res = generate_text(model=self.llm_model, model_inputs=input)

        res = decode_generated_text(
            generated_ids=gen_res,
            tokenizer=self.tokenizer,
        )

        return res
