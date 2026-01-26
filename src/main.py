from fastapi import FastAPI
from dotenv import load_dotenv
from src.database import engine, Base
#must imported:
from src.worker import worker
from src.models_loader import *
#routers:
from src.features.indexer.router import router as indexer_router

load_dotenv()

app = FastAPI()
app.include_router(router=indexer_router)
# Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)