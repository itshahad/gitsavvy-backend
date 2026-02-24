from fastapi import FastAPI
from dotenv import load_dotenv

from sqlalchemy import text
from src.database import engine, Base

# must imported:
from src.worker import worker  # type: ignore
from src.models_loader import *

# routers:
from src.features.indexer.router import router as indexer_router
from src.features.documentation_generator.router import router as docs_router

load_dotenv()

app = FastAPI()
app.include_router(router=indexer_router)
app.include_router(router=docs_router)
# with engine.begin() as conn:
#     conn.execute(text("DROP TABLE IF EXISTS documentation CASCADE"))
# Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
