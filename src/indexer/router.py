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


from fastapi import APIRouter
from .service import IndexerService

router = APIRouter()

@router.get("/")
def test():
    # return get_repo_metadata("django", "django")
    # return download_repo("octocat", "Hello-World", "master")
    # return download_repo("shahadio", "quizu")
    # return is_selected("/gitsavvy-backend/src/cindexe/router.py")
    # return select_repo_files("repos/django.zip", "django")
    # return chunk_text_files(file_path="repos/django/django-django-f3b982f/docs/index.txt", chunk_size=20, overlapping=5)
    indx=IndexerService()
    return indx.chunk_repo_files(zip_file_path="repos/quizu.zip", repo_name="quizu")