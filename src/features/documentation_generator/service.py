from typing import Any, Iterable
from sqlalchemy.orm import Session
from sqlalchemy import case, or_

from src.features.documentation_generator.llm import create_docs_generation_prompt, create_model_input, decode_generated_text, generate_text  # type: ignore
from src.features.documentation_generator.models import Documentation
from src.features.documentation_generator.schemas import DocCreate, DocRead
from src.features.documentation_generator.utils import decode_doc_json
from src.features.indexer.models import Chunk, ChunkType, File
from src.features.indexer.constants import AST_LANG_EXT


class DocGenerateService:
    def __init__(
        self, session: Session, repo_id: int, llm_service: "LlmService"
    ) -> None:
        self.session = session
        self.repo_id = repo_id
        self.llm_service = llm_service

    def load_files(self, batch_size: int = 50):
        q = (
            self.session.query(File)
            .filter(
                File.repository_id == self.repo_id,
                or_(*[File.file_path.endswith(ext) for ext in AST_LANG_EXT]),
            )
            .order_by(File.id)
            .execution_options(stream_results=True)
            .yield_per(batch_size)
        )

        yielded = False
        for f in q:
            yielded = True
            yield f

        if not yielded:
            raise ValueError("No files found")

    def load_file_chunks(self, file: File, batch_size: int = 50):
        type_order = case(
            (Chunk.type == ChunkType.FUNCTION_INNER_BLOCK, 0),
            (Chunk.type == ChunkType.FUNCTION, 1),
            (Chunk.type == ChunkType.CLASS_SUMMARY, 2),
            (Chunk.type == ChunkType.FILE_SUMMARY, 3),
            (Chunk.type == ChunkType.TEXT, 4),
            else_=99,
        )

        q = (
            self.session.query(Chunk)
            .filter(Chunk.file_id == file.id)
            .order_by(type_order)
            .execution_options(stream_results=True)
            .yield_per(batch_size)
        )

        yielded = False
        for c in q:
            yielded = True
            yield c

        if not yielded:
            raise ValueError("No chunks found")

    def generate_chunks_docs(self, chunks_list: Iterable[Chunk]):
        docs: list[DocRead] = []
        for chunk in chunks_list:
            if (
                chunk.type == ChunkType.FUNCTION
                or chunk.type == ChunkType.FUNCTION_INNER_BLOCK
            ):
                res = self.llm_service.generate_llm_response(chunk=chunk)
                print(res)
                short_summary, detailed_doc = decode_doc_json(json_str=res)
                doc_artifact = self.store_doc_artifact(
                    chunk=chunk, short_summary=short_summary, detailed_doc=detailed_doc
                )
                docs.append(DocRead.model_validate(doc_artifact))
        return docs

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
        return doc_db


class LlmService:
    def __init__(self, session: Session, llm_model: Any, tokenizer: Any) -> None:
        self.session = session
        self.llm_model = llm_model
        self.tokenizer = tokenizer

    def generate_llm_response(self, chunk: Chunk):
        prompt = create_docs_generation_prompt(
            file_path=chunk.file_path, content=chunk.content
        )

        input = create_model_input(
            messages=prompt, tokenizer=self.tokenizer, model=self.llm_model
        )

        gen_res = generate_text(model=self.llm_model, model_inputs=input)

        res = decode_generated_text(
            generated_ids=gen_res,
            tokenizer=self.tokenizer,
        )

        return res
