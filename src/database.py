from sqlalchemy import create_engine
import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase

USERNAME = os.getenv("DB_USERNAME", "postgres")
PASSWORD = os.getenv("DB_PASSWORD", "postgres")
PORT = os.getenv("DB_PORT", 5432)
HOST = os.getenv("DB_HOST", "db")
DBNAME = os.getenv("DB_NAME", "postgres")

SQLALCHEMY_DB_URL = f"postgresql+psycopg2://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}"

engine = create_engine(SQLALCHEMY_DB_URL)
SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)
Base = declarative_base() #to construct tables with classes

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Base(DeclarativeBase):
    pass