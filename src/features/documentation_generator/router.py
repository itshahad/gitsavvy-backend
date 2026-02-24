from fastapi import APIRouter, Depends, HTTPException

# import requests
from sqlalchemy.orm import Session
from src.database import get_db
from src.features.documentation_generator.tasks import docs_generator


router = APIRouter()


@router.get("/docs-gen")
def test(session: Session = Depends(get_db)):
    try:
        repo_id = 2
        repo_name = "fastapi"
        start_from_module = 607
        start_from_file_id = 4609
        start_from_chunk_id = 11590
        docs_generator.delay(  # type: ignore
            repo_id=repo_id,
            repo_name=repo_name,
            start_from_module=start_from_module,
            start_from_file=start_from_file_id,
            start_from_chunk=start_from_chunk_id,
        )
        return {"meow": "meow"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
