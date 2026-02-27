from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.features.chatbot.constants import SYS_PROMPT_CHATBOT

from src.features.documentation_generator.llm import generate_llm_response
from src.features.indexer.models import Chunk, ChunkEmbedding
from src.features.indexer.tasks import EmbeddingService


class ChatbotService:
    def __init__(
        self,
        db_session: Session,
        embedder: Any,
        embedding_tokenizer: Any,
        repo_id: int,
        llm_model: Any,
        llm_tokenizer: Any,
        k: int = 8,
    ) -> None:
        self.llm_model = llm_model
        self.llm_tokenizer = llm_tokenizer
        self.repo_id = repo_id
        self.k = k
        self.db_session = db_session
        self.embedding_service = EmbeddingService(
            db_session=db_session, embedder=embedder, tokenizer=embedding_tokenizer
        )

    def embed_query(self, query: str):
        vec, meta = self.embedding_service.embed_text(text=query)
        print(meta)
        return vec

    def vector_search_chunks(
        self, repo_id: int, query_embedding: list[float], k: int = 8
    ):
        filters = [Chunk.repo_id == repo_id]

        stmt = (
            select(
                Chunk,
                ChunkEmbedding.embedding_vector.l2_distance(query_embedding).label(
                    "distance"
                ),
            )
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == Chunk.id)
            .where(*filters)
            .order_by("distance")
            .limit(k)
        )

        rows = self.db_session.execute(stmt).all()
        return rows

    def get_relevant_documents(self, query: str):
        query_embedding = self.embed_query(query)

        rows = self.vector_search_chunks(
            repo_id=self.repo_id, query_embedding=query_embedding, k=self.k
        )

        chunks: list[Chunk] = [row[0] for row in rows]

        return chunks

    def format_context(self, chunks: list[Chunk]):
        chunks_set: set[int] = set()
        parts: list[str] = []
        for chunk in chunks:
            if chunk.id in chunks_set:
                continue
            chunks_set.add(chunk.id)
            header = f"[{chunk.type} {chunk.file_id} #{chunk.id}]"
            parts.append(header + "\n" + chunk.content_text)
        return "\n\n---\n\n".join(parts)

    def run_chatbot(self, query: str):
        chunks = self.get_relevant_documents(query=query)

        context = self.format_context(chunks=chunks)

        USER_PROMPT = f"Question: {query}\n\nContext:\n{context}"

        res = generate_llm_response(
            model=self.llm_model,
            tokenizer=self.llm_tokenizer,
            sys_prompt=SYS_PROMPT_CHATBOT,
            usr_prompt=USER_PROMPT,
        )

        return res
