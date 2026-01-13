from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey
from typing import List

class Base(DeclarativeBase):
    pass

class Repository(Base):
    __tablename__ = "repository"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(30))
    description: Mapped[str]
    url: Mapped[str]
    forks_count: Mapped[int]
    open_issues_count: Mapped[int]
    default_branch: Mapped[str] = mapped_column(String(30))
    avatar_url: Mapped[str]

    files: Mapped[List["File"]] = relationship(back_populates="repository")

    def __repr__(self):
        return f"Repository(id={self.id!r}, owner={self.owner!r}, name={self.name!r}, description={self.description!r}, url={self.url!r}, forks_count={self.forks_count!r}, open_issues_count={self.open_issues_count!r}, default_branch={self.default_branch!r}, avatar_url={self.avatar_url!r})"



class File(Base):
    __tablename__ = "file"

    id: Mapped[int] = mapped_column(primary_key=True)

    repository_id: Mapped[int] = mapped_column(ForeignKey("repository.id"))
    repository: Mapped["Repository"] = relationship(back_populates="files")

    commit_sha: Mapped[str] 
    file_path: Mapped[str]
    language: Mapped[str]
    content_hash: Mapped[str]

    chunks = Mapped[List["Chunk"]] = relationship(back_populates="file")

    def __repr__(self):
        return super().__repr__()
    

class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[int] = mapped_column(primary_key=True)

    file_id: Mapped[int] = mapped_column(ForeignKey("file.id"))
    file: Mapped["File"] = relationship(back_populates="chunks")

    chunk_parent_id: Mapped[int] = mapped_column(ForeignKey("chunk.id"))
    chunk_parent: Mapped["Chunk"] = relationship(back_populates="children_chunks", remote_side=[id])
    children_chunks: Mapped[List["Chunk"]] = relationship(back_populates="chunk_parent")




