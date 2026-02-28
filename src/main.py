#root of the project, which inits the FastAPI app
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from database import engine, Base
# from indexer.models import *
# from indexer.router import router
from authentication.models import User
from authentication.router import router as auth_router



app = FastAPI()
app.include_router(auth_router)
# app.include_router(router=router)
# Base.metadata.drop_all(engine)
Base.metadata.create_all(bind=engine)
@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}
