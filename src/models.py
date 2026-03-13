from datetime import datetime

from sqlalchemy import Column, Integer
from sqlalchemy.sql import func
from src.database import Base
from sqlalchemy.orm import Mapped, mapped_column


class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
