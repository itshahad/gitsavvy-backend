from pydantic import BaseModel, ConfigDict

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
