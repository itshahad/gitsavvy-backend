#root of the project, which inits the FastAPI app
from fastapi import FastAPI
from dotenv import load_dotenv
from database import engine, Base
from features.indexer.models import *
from features.indexer.router import router
from worker import worker

load_dotenv()

app = FastAPI()
app.include_router(router=router)
# Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)