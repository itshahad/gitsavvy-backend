from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase
from config import SQLALCHEMY_DB_URL

engine = create_engine(SQLALCHEMY_DB_URL)
SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)

class Base(DeclarativeBase): #to construct tables with classes
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()