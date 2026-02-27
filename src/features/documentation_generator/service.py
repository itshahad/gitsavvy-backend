from typing import Any, Generator
from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from src.exceptions import DatabaseError
from src.features.documentation_generator.exceptions import RepoNotFound
from src.features.documentation_generator.llm import generate_llm_response  # type: ignore

from src.features.documentation_generator.models import Documentation
from src.features.documentation_generator.schemas import DocCreate
from src.features.documentation_generator.schemas import DocRead
from src.features.documentation_generator.utils import parse_yaml_front_matter
from src.features.indexer.models import Chunk, Module, ChunkType, File
from src.features.indexer.constants import AST_LANG_EXT
from src.features.indexer.router import FileRead, Path, get_file_complete_path
from src.features.indexer.schemas import ModuleRead, RepoRead
from src.features.indexer.service import normalize_repo_path
from src.models_loader import OutlineType, Repository


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


class DocsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_repo(self, repo_id: int):
        repo = self.db.get(Repository, repo_id)
        if repo is None:
            raise RepoNotFound(repo_id=repo_id)
        return RepoRead.model_validate(repo)

    def get_modules(
        self, repo_id: int, limit: int | None = 20, cursor: int | None = None
    ):
        try:
            self.get_repo(repo_id=repo_id)
            filters = [Module.repository_id == repo_id]
            if cursor:
                filters.append(Module.id > cursor)
            stmt = select(Module).where(*filters).order_by(Module.id).limit(limit)

            modules = self.db.execute(stmt).scalars().all()

            return [ModuleRead.model_validate(module) for module in modules]
        except SQLAlchemyError as e:
            raise DatabaseError from e


# class LlmService:
#     def __init__(self, session: Session, llm_model: Any, tokenizer: Any) -> None:
#         self.session = session
#         self.llm_model = llm_model
#         self.tokenizer = tokenizer

#     def generate_llm_response(self, file_path: str, content: str) -> str:
#         prompt = create_prompt(file_path=file_path, content=content)
#         full_text = apply_chat_template(messages=prompt, tokenizer=self.tokenizer)
#         print(f"full_text {full_text}")

#         if safe_prompt(tokenizer=self.tokenizer, text=full_text):
#             model_inputs = create_model_input(
#                 text=full_text, tokenizer=self.tokenizer, model=self.llm_model
#             )
#             gen_ids = generate_text(
#                 model=self.llm_model, model_inputs=model_inputs, max_new_tokens=512
#             )
#             return decode_generated_text(
#                 generated_ids=gen_ids, tokenizer=self.tokenizer
#             )

#         parts = split_huge_text(content)
#         partial_summaries: list[str] = []

#         for part in parts:
#             part_prompt = create_prompt(file_path=file_path, content=part)
#             part_text = apply_chat_template(
#                 messages=part_prompt, tokenizer=self.tokenizer
#             )
#             print(f"part_text {part_text}")

#             if not safe_prompt(self.tokenizer, part_text):
#                 subparts = split_huge_text(part, max_bytes=3_000)
#                 for sp in subparts:
#                     sp_prompt = create_prompt(file_path=file_path, content=sp)
#                     sp_text = apply_chat_template(
#                         messages=sp_prompt, tokenizer=self.tokenizer
#                     )
#                     if not safe_prompt(tokenizer=self.tokenizer, text=sp_text):
#                         sp_ids = self.tokenizer(
#                             sp_text,
#                             return_tensors="pt",
#                             truncation=True,
#                             max_length=MAX_INPUT_TOKENS,
#                         ).to(self.llm_model.device)
#                         gen_ids = generate_text(
#                             model=self.llm_model,
#                             model_inputs=sp_ids,
#                             max_new_tokens=256,
#                         )
#                     else:
#                         sp_inputs = create_model_input(
#                             sp_text, self.tokenizer, self.llm_model
#                         )
#                         gen_ids = generate_text(
#                             model=self.llm_model,
#                             model_inputs=sp_inputs,
#                             max_new_tokens=256,
#                         )
#                     partial_summaries.append(
#                         decode_generated_text(
#                             generated_ids=gen_ids, tokenizer=self.tokenizer
#                         )
#                     )
#                 continue

#             part_inputs = create_model_input(
#                 text=part_text, tokenizer=self.tokenizer, model=self.llm_model
#             )
#             gen_ids = generate_text(
#                 model=self.llm_model, model_inputs=part_inputs, max_new_tokens=256
#             )
#             partial_summaries.append(
#                 decode_generated_text(generated_ids=gen_ids, tokenizer=self.tokenizer)
#             )

#         merged_content = "\n\n".join(
#             f"- {s.strip()}" for s in partial_summaries if s.strip()
#         )
#         merge_prompt = create_prompt(
#             file_path=file_path,
#             sys_prompt=SYS_PROMPT_COMBINE_DOCS,
#             usr_prompt=f"{merged_content}",
#         )
#         merge_text = apply_chat_template(
#             messages=merge_prompt, tokenizer=self.tokenizer
#         )

#         model_inputs = create_model_input(
#             text=merge_text, tokenizer=self.tokenizer, model=self.llm_model
#         )
#         gen_ids = generate_text(
#             model=self.llm_model, model_inputs=model_inputs, max_new_tokens=512
#         )
#         return decode_generated_text(generated_ids=gen_ids, tokenizer=self.tokenizer)
