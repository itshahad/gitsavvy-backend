from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from .exceptions import RepoNotFoundError
from features.indexer.tasks import indexer as indexer_task


router = APIRouter()

@router.get("/")
def test(session: Session = Depends(get_db)):
    try:
        indexer_task.delay("django", "django")
        return {
            "yay": "yay"
        }
    except RepoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

