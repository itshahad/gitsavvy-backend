import uuid

from fastapi import APIRouter, WebSocket

# import requests
from src.features.chatbot.tasks import chatbot_task
from src.features.chatbot.utils import relay_pubsub

router = APIRouter(prefix="/chatbot")


# @router.get("/chatbot")
# def test(session: Session = Depends(get_db)):
#     try:
#         repo_id = 2
#         result = chatbot_task.delay(repo_id=repo_id)  # type: ignore
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=404, detail=str(e))


@router.websocket("/ws")
async def chatbot(ws: WebSocket):
    await ws.accept()
    init = await ws.receive_json()

    redis = ws.app.state.redis

    repo_id = int(init["repo_id"])
    query = str(init["query"])

    job_id = uuid.uuid4().hex
    channel = f"chat:{job_id}"

    chatbot_task.delay(repo_id=repo_id, query=query, channel=channel)  # type: ignore

    await ws.send_json({"type": "started", "job_id": job_id})

    await relay_pubsub(channel, ws, redis=redis)
