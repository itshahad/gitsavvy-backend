from fastapi import APIRouter, Depends, HTTPException

# import requests
from sqlalchemy.orm import Session
from src.database import get_db
from src.features.documentation_generator.tasks import docs_generator


router = APIRouter()


@router.get("/docs-gen")
def test(session: Session = Depends(get_db)):
    try:
        repo_id = 1
        docs_generator.delay(repo_id)  # type: ignore
        return {"meow": "meow"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
