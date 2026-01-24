#a core of each module with all the endpoints

# from fastapi import APIRouter, Depends
# from sqlalchemy.orm import Session
# from database import get_db
# from feature.schemas import UserCreate, UserResponse
# from feature.service import create_user, list_users

# router = APIRouter()

# @router.post("/", response_model=UserResponse)
# def create(data: UserCreate, db: Session = Depends(get_db)):
#     return create_user(db, data)

# @router.get("/", response_model=list[UserResponse])
# def list_all(db: Session = Depends(get_db)):
#     return list_users(db)


from fastapi import APIRouter, Depends, HTTPException
from .service import IndexerService
from sqlalchemy.orm import Session
from database import get_db
from .exceptions import RepoNotFoundError
from features.indexer.tasks import indexer as indexer_task


router = APIRouter()

@router.get("/")
def test(session: Session = Depends(get_db)):
    try:
        indexer_task.delay()
        return {
            "yay": "yay"
        }
        # indx=IndexerService()
        # return indx.get_repo_metadata("django", "django", session)
        # return indx.download_repo("django", "django")
        # return indx.select_repo_files(session, repo_id=1, zip_file_path="repos/django.zip", repo_name="django", commit_sha="0d31ca98830542088299d2078402891d08cc3a65")
        # return chunk_text_files(file_path="repos/django/django-django-f3b982f/docs/index.txt", chunk_size=20, overlapping=5)
        # return indx.chunk_repo_files(session, zip_file_path="repos/django.zip", repo_name="django", repo_id=1,commit_sha="0d31ca98830542088299d2078402891d08cc3a65")
    except RepoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

