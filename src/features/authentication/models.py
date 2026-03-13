
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.database import engine, Base

class User(Base):
    __tablename__ = "user"

   
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Firebase identity (ثابت)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    github_id: Mapped[int] = mapped_column(Integer, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    
    github_access_token_enc: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")