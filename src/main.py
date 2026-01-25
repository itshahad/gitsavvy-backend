from fastapi import FastAPI
from dotenv import load_dotenv
from database import engine, Base
#must imported:
from worker import worker
from models import *
#routers:
from features.indexer.router import router as indexer_router

load_dotenv()

app = FastAPI()
app.include_router(router=indexer_router)
# Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)