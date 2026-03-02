from dataclasses import dataclass

from src.features.indexer.models import Chunk


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float
