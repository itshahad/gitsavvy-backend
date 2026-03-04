from pydantic import BaseModel, field_validator, ConfigDict

from src.core.validators import validate_sha
from .models import ChunkType


# ====================================================================


class ChunkModel(BaseModel):
    file_id: int
    repo_id: int
    chunk_parent_id: int | None = None
    start_byte: int | None = None
    end_byte: int | None = None
    type: ChunkType
    content: str
    content_json: list[dict[str, int | str]] | None = None
    content_text_hash: str | None = None
    signature: str | None = None
    language: str | None = None

    @field_validator("content_text_hash", mode="after")
    @classmethod
    def validate_commit_content(cls, v: str) -> str:
        return validate_sha(v)


class ChunkCreate(ChunkModel):
    pass


class ChunkRead(ChunkModel):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ====================================================================


class ChunkEmbeddingModel(BaseModel):
    chunk_id: int
    embedding_vector: list[float]


class ChunkEmbeddingCreate(ChunkEmbeddingModel):
    pass


class ChunkEmbeddingRead(ChunkEmbeddingModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
