#MODELS IMPORT FOR TABLE CREATION:
from features.indexer.models import *


#======================================================================================
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func
from database import Base

class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    