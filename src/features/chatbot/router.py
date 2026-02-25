from fastapi import APIRouter, Depends, HTTPException

# import requests
from sqlalchemy.orm import Session
from src.database import get_db
from src.features.chatbot.tasks import chatbot_task


router = APIRouter()


@router.get("/chatbot")
def test(session: Session = Depends(get_db)):
    try:
        answer = chatbot_task.delay(repo_id=2)  # type: ignore
        return answer
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
