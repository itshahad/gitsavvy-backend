from fastapi import FastAPI
from dotenv import load_dotenv
from redis.asyncio import Redis


from src.config import CELERY_BROKER_URL
from src.database import engine, Base

# must imported:
from src.worker import worker  # type: ignore
from src.models_loader import *

# routers:
from src.features.indexer.router import router as indexer_router
from src.features.documentation_generator.router import router as docs_router
from src.features.chatbot.router import router as chatbot_router
from src.features.repositories.router import router as repositories_router

load_dotenv()

app = FastAPI()


@app.on_event("startup")  # type: ignore
async def startup():
    app.state.redis = Redis.from_url(f"{CELERY_BROKER_URL}/0", decode_responses=True)  # type: ignore
    print("API Redis connected")


@app.on_event("shutdown")  # type: ignore
async def shutdown():
    await app.state.redis.close()
    print("API Redis closed")


# app.include_router(chatbot_router)
app.include_router(router=indexer_router)
app.include_router(router=repositories_router)
app.include_router(router=docs_router)
app.include_router(router=chatbot_router)
# with engine.begin() as conn:
#     conn.execute(text("DROP TABLE IF EXISTS documentation CASCADE"))
# Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
