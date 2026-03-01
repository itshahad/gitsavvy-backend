from pydantic import BaseModel, ConfigDict

from src.models_loader import ChunkType

# ====================================================================


class DocumentationModel(BaseModel):
    chunk_id: int
    short_summary: str
    detailed_doc: str


class DocCreate(DocumentationModel):
    pass


class DocRead(DocumentationModel):
    model_config = ConfigDict(from_attributes=True)

    id: int


class DocModel(BaseModel):
    chunk_id: int
    doc_id: int
    chunk_parent_id: int | None = None
    start_byte: int | None = None
    end_byte: int | None = None
    signature: str | None = None
    docs: str
    code: str | None = None
    type: ChunkType
