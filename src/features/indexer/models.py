from dataclasses import dataclass

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Enum as SqlEnum, UniqueConstraint
from typing import TYPE_CHECKING, List
from enum import Enum
from src.models import BaseModel
from pgvector.sqlalchemy import Vector  # type: ignore
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from src.features.documentation_generator.models import Documentation
    from src.features.repositories.models import Repository


class OutlineType(Enum):
    Function = "function"
    STMT = "statement"
    CLASS = "class"
    SIGN = "sign"


@dataclass(frozen=True)
class Outline:
    start_byte: int
    end_byte: int
    content: str
    type: OutlineType


class ChunkType(Enum):
    # FUNCTION_INNER_BLOCK = "function_inner_block"
    FUNCTION = "function"
    CLASS_SUMMARY = "class_summary"
    FILE_SUMMARY = "file_summary"
    TEXT = "text"


# ====================================================================


class Module(BaseModel):
    __tablename__ = "module"

    __table_args__ = (UniqueConstraint("repository_id", "module_parent_id", "path"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    repository_id: Mapped[int] = mapped_column(ForeignKey("repository.id"))
    repository: Mapped["Repository"] = relationship(back_populates="modules")

    path: Mapped[str]

    files: Mapped[List["File"]] = relationship(
        back_populates="module", cascade="all, delete-orphan"
    )

    module_parent_id: Mapped[int] = mapped_column(
        ForeignKey("module.id"), nullable=True
    )
    module_parent: Mapped["Module"] = relationship(
        back_populates="children_modules", remote_side=[id]
    )
    children_modules: Mapped[List["Module"]] = relationship(
        back_populates="module_parent", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"File(id={self.id!r}, repository_id={self.repository_id!r}, path={self.path!r})"


# --------------------------------------------------------------


class File(BaseModel):
    __tablename__ = "file"

    __table_args__ = (UniqueConstraint("repository_id", "file_path", name="uq_file"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    repository_id: Mapped[int] = mapped_column(ForeignKey("repository.id"))
    repository: Mapped["Repository"] = relationship(back_populates="files")

    module_id: Mapped[int] = mapped_column(ForeignKey("module.id"))
    module: Mapped["Module"] = relationship(back_populates="files")

    commit_sha: Mapped[str]
    file_path: Mapped[str]
    content_hash: Mapped[str] = mapped_column(nullable=True)

    chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"File(id={self.id!r}, repository_id={self.repository_id!r}, commit_sha={self.commit_sha!r}, file_path={self.file_path!r}, content_hash={self.content_hash!r})"


# --------------------------------------------------------------


class Chunk(BaseModel):
    __tablename__ = "chunk"

    id: Mapped[int] = mapped_column(primary_key=True)

    file_id: Mapped[int] = mapped_column(ForeignKey("file.id"))
    file: Mapped["File"] = relationship(back_populates="chunks")

    repo_id: Mapped[int] = mapped_column(ForeignKey("repository.id"))
    repository: Mapped["Repository"] = relationship(back_populates="chunks")

    chunk_parent_id: Mapped[int] = mapped_column(ForeignKey("chunk.id"), nullable=True)
    chunk_parent: Mapped["Chunk"] = relationship(
        back_populates="children_chunks", remote_side=[id]
    )
    children_chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="chunk_parent", cascade="all, delete-orphan"
    )

    start_byte: Mapped[int] = mapped_column(nullable=True)
    end_byte: Mapped[int] = mapped_column(nullable=True)
    type: Mapped["ChunkType"] = mapped_column(SqlEnum(ChunkType))
    content_text: Mapped[str]
    content_json: Mapped[list[dict[str, int | str]]] = mapped_column(
        JSONB, nullable=True
    )
    content_text_hash: Mapped[str] = mapped_column(nullable=True)

    embedding: Mapped["ChunkEmbedding"] = relationship(
        back_populates="chunk", cascade="all, delete-orphan", uselist=False
    )

    documentation: Mapped["Documentation"] = relationship(
        back_populates="chunk", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self):
        return f"Chunk(id={self.id!r}, repo_id={self.repo_id!r}, file_id={self.file_id!r}, chunk_parent_id={self.chunk_parent_id!r}, start_byte={self.start_byte!r}, end_byte={self.end_byte!r}, type={self.type!r}, content_text={self.content_text!r},content_json={self.content_json!r}, content_text_hash={self.content_text_hash!r})"


# --------------------------------------------------------------


class ChunkEmbedding(BaseModel):
    __tablename__ = "chunk_embedding"

    id: Mapped[int] = mapped_column(primary_key=True)
    embedding_vector: Mapped[list[float]] = mapped_column(Vector(1536))

    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunk.id"), unique=True)
    chunk: Mapped["Chunk"] = relationship(back_populates="embedding")

    def __repr__(self):
        return f"ChunkEmbedding(id={self.id!r}, chunk_id={self.chunk_id!r}, embedding_vector={self.embedding_vector!r})"


# --------------------------------------------------------------


class RepositoryTopic(BaseModel):
    __tablename__ = "repository_topic"

    id: Mapped[int] = mapped_column(primary_key=True)

    repository_id: Mapped[int] = mapped_column(ForeignKey("repository.id"))
    repository: Mapped["Repository"] = relationship(back_populates="topics")

    # UserId
    topic: Mapped[str]

    def __repr__(self):
        return f"RepositoryTopic(id={self.id!r}, repository_id={self.repository_id!r}, topic={self.topic!r})"
