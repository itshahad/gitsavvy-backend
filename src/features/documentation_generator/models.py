from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
from src.models import BaseModel

# ====================================================================
if TYPE_CHECKING:
    from src.features.indexer.models import Chunk


class Documentation(BaseModel):
    __tablename__ = "documentation"

    id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunk.id"), unique=True)
    chunk: Mapped["Chunk"] = relationship(back_populates="documentation")

    short_summary: Mapped[str]
    detailed_doc: Mapped[str]

    def __repr__(self):
        return f"Documentation(id={self.id!r}, chunk_id={self.chunk_id!r}, short_summary={self.short_summary!r}, detailed_doc={self.detailed_doc!r})"
