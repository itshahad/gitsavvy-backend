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
