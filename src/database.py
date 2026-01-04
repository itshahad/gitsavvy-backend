from sqlalchemy import create_engine
import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base


USERNAME = os.getenv("DB_USERNAME")
PASSWORD = os.getenv("DB_PASSWORD")
PORT = os.getenv("DB_PORT", 5432)


SQLALCHEMY_DB_URL = f"postgresql://{USERNAME}:{PASSWORD}@host:{PORT}/postgres"


engine = create_engine(SQLALCHEMY_DB_URL)


SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)

Base = declarative_base() #to construct tables with classes

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

