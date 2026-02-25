from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda


from src.features.indexer.models import Chunk, ChunkEmbedding
from src.features.indexer.tasks import EmbeddingService


class ChatbotService:
    def __init__(
        self, db_session: Session, embedding_service: EmbeddingService
    ) -> None:
        self.db_session = db_session
        self.embedding_service = embedding_service

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


class ChunkRetriever(BaseRetriever):
    def __init__(
        self,
        *,
        db_session: Session,
        repo_id: int,
        embedder: Any,
        tokenizer: Any,
        llm: Any,
        k: int = 8,
    ) -> None:
        super().__init__()
        self.db_session = db_session
        self.embedding_service = EmbeddingService(
            db_session=db_session, embedder=embedder, tokenizer=tokenizer
        )
        self.chatbot_service = ChatbotService(
            db_session=db_session, embedding_service=self.embedding_service
        )
        self.repo_id = repo_id
        self.llm = llm
        self.k = k

    def _get_relevant_documents(self, query: str, *, run_manager=None):  # type: ignore
        query_embedding = self.chatbot_service.embed_query(query)

        rows = self.chatbot_service.vector_search_chunks(
            repo_id=self.repo_id, query_embedding=query_embedding, k=self.k
        )

        chunks: list[Chunk] = [row[0] for row in rows]

        docs: list[Document] = []
        for chunk in chunks:
            docs.append(
                Document(
                    page_content=chunk.content_text,
                    metadata={
                        "chunk_id": chunk.id,
                        "repo_id": chunk.repo_id,
                        "parent_id": chunk.chunk_parent_id,
                        "file_id": chunk.file_id,
                        "type": chunk.type,
                    },
                )
            )
        return docs

    def format_docs(self, docs: list[Document]):
        chunks_set: set[int] = set()
        parts: list[str] = []
        for doc in docs:
            chunk_id = doc.metadata.get("chunk_id")  # type: ignore
            if chunk_id in chunks_set:
                continue
            chunks_set.add(chunk_id)  # type: ignore
            header = f"[{doc.metadata.get('type')} {doc.metadata.get('file_id')} #{chunk_id}]"  # type: ignore
            parts.append(header + "\n" + doc.page_content)
        return "\n\n---\n\n".join(parts)

    def run_chain(self, query: str):
        prompt = ChatPromptTemplate.from_messages(  # type: ignore
            [
                (
                    "system",
                    "You are a GitSavvy repository assistant. "
                    "Answer ONLY using the provided context. "
                    "If the context doesn't contain the answer, say you don't know and suggest what to search next.",
                ),
                ("human", "Question: {question}\n\nContext:\n{context}"),
            ]
        )

        format_docs_runnable = RunnableLambda(self.format_docs)

        rag_chain = (
            {
                "context": self | format_docs_runnable,
                "question": RunnablePassthrough(),
            }
            | prompt
            | self.llm
        )

        return rag_chain.invoke(query)
