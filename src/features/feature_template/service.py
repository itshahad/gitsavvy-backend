#module specific business logic

# from sqlalchemy.orm import Session
# from feature.models import User
# from feature.schemas import UserCreate
# from feature.exceptions import FeatureException

# def create_user(db: Session, data: UserCreate):
#     if db.query(User).filter(User.email == data.email).first():
#         raise FeatureException("Email already exists")

#     user = User(**data.dict())
#     db.add(user)
#     db.commit()
#     db.refresh(user)
#     return user

# def list_users(db: Session):
#     return db.query(User).all()
