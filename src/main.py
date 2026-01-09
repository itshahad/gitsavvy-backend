#root of the project, which inits the FastAPI app
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()


# @app.get("/")
# async def root():
#     return {"message": "Hello World"}


from indexer.router import router

app.include_router(router=router)