from pydantic import BaseModel, ConfigDict

from src.features.indexer.schemas import ChunkRead

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


class DocChunkRead(DocumentationModel):
    model_config = ConfigDict(from_attributes=True)
    chunk: ChunkRead
    id: int
