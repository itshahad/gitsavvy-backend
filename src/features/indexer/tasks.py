from worker import worker
from sqlalchemy.orm import Session
from .service import IndexerService
from database import SessionLocal


@worker.task(name="indexer.entry", queue="gpu_queue")
def indexer():
    session = SessionLocal()
    indx = IndexerService()
    val = indx.get_repo_metadata("django", "django", session)
    print(val)

