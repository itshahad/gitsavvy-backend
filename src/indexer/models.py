from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Enum as SqlEnum, JSON
from typing import List
from enum import Enum
from database import Base 

class ChunkType(Enum):
    FUNCTION = "function"
    CLASS_SUMMARY = "class_summary"
    FILE_SUMMARY = "file_summary"
    TEXT = "text"

# class Base(DeclarativeBase):
#     pass

class Repository(Base):
    __tablename__ = "repository"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(nullable=True)
    url: Mapped[str]
    forks_count: Mapped[int] = mapped_column(nullable=True)
    open_issues_count: Mapped[int] = mapped_column(nullable=True)
    default_branch: Mapped[str] = mapped_column(String(30))
    avatar_url: Mapped[str] = mapped_column(nullable=True)

    files: Mapped[List["File"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    topics: Mapped[List["RepositoryTopic"]] = relationship(back_populates="repository", cascade="all, delete-orphan")

    def __repr__(self):
        return f"Repository(id={self.id!r}, owner={self.owner!r}, name={self.name!r}, description={self.description!r}, url={self.url!r}, forks_count={self.forks_count!r}, open_issues_count={self.open_issues_count!r}, default_branch={self.default_branch!r}, avatar_url={self.avatar_url!r})"
    

class File(Base):
    __tablename__ = "file"

    id: Mapped[int] = mapped_column(primary_key=True)

    repository_id: Mapped[int] = mapped_column(ForeignKey("repository.id"))
    repository: Mapped["Repository"] = relationship(back_populates="files")

    commit_sha: Mapped[str] 
    file_path: Mapped[str]
    content_hash: Mapped[str] = mapped_column(nullable=True)

    chunks: Mapped[List["Chunk"]] = relationship(back_populates="file", cascade="all, delete-orphan")

    def __repr__(self):
        return f"File(id={self.id!r}, repository_id={self.repository_id!r}, commit_sha={self.commit_sha!r}, file_path={self.file_path!r}, content_hash={self.content_hash!r})"

class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[int] = mapped_column(primary_key=True)

    file_id: Mapped[int] = mapped_column(ForeignKey("file.id"))
    file: Mapped["File"] = relationship(back_populates="chunks")

    chunk_parent_id: Mapped[int] = mapped_column(ForeignKey("chunk.id"), nullable=True)
    chunk_parent: Mapped["Chunk"] = relationship(back_populates="children_chunks", remote_side=[id])
    children_chunks: Mapped[List["Chunk"]] = relationship(back_populates="chunk_parent", cascade="all, delete-orphan")

    start_line: Mapped[int] = mapped_column(nullable=True)
    end_line: Mapped[int] = mapped_column(nullable=True)
    type: Mapped['ChunkType'] = mapped_column(SqlEnum(ChunkType))
    content: Mapped[str]
    embedding_vector: Mapped[List[int]] = mapped_column(JSON, nullable=True)
    content_hash: Mapped[str] = mapped_column(nullable=True)

    def __repr__(self):
        return f"Chunk(id={self.id!r}, file_id={self.file_id!r}, chunk_parent_id={self.chunk_parent_id!r}, start_line={self.start_line!r}, end_line={self.end_line!r}, type={self.type!r}, content={self.content!r}, embedding_vector={self.embedding_vector!r}, content_hash={self.content_hash!r})"
    
class RepositoryTopic(Base):
    __tablename__ = "repository_topic"

    id: Mapped[int] = mapped_column(primary_key=True)

    repository_id: Mapped[int] = mapped_column(ForeignKey("repository.id"))
    repository: Mapped["Repository"] = relationship(back_populates="topics")

    #UserId
    topic: Mapped[str]

    def __repr__(self):
        return f"RepositoryTopic(id={self.id!r}, repository_id={self.repository_id!r}, topic={self.topic!r})"
