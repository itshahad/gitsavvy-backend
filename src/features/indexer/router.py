from fastapi import APIRouter, Depends, HTTPException

# import requests
from sqlalchemy.orm import Session
from src.database import get_db
from src.features.indexer.tasks import index_repo
from src.features.repositories.exceptions import RepoNotFoundError  # type: ignore


router = APIRouter(prefix="/indexer")


# @router.get("/repo")
# def test(session: Session = Depends(get_db)):
#     try:
#         indexer.delay("fastapi", "fastapi")  # type: ignore
#         return {"yay": "yay"}
#     except RepoNotFoundError as e:
#         raise HTTPException(status_code=404, detail=str(e))


# @router.get("/revoke")
# def revoke_celery_task():
#     task_id = "fd574049-b2b5-49a1-87a3-0f34088e6901"
#     worker.control.revoke(task_id, terminate=True)  # type: ignore
#     return {"Message": f"Revoked Task {task_id}"}
