from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database import get_db
from src.features.indexer.exceptions import RepoNotFoundError
from src.features.indexer.tasks import indexer  # type: ignore


router = APIRouter()


@router.get("/")
def test(session: Session = Depends(get_db)):
    try:
        indexer.delay("Git-Savvy", "test")  # type: ignore
        return {"yay": "yay"}
    except RepoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
