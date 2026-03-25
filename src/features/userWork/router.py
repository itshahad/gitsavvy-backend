from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.features.authentication.dependencies import get_current_user
from src.features.userWork.schemas import MyWorkResponse
from src.features.userWork.services import MyWorkService

router = APIRouter(prefix="/my-work", tags=["my-work"])


@router.get("", response_model=MyWorkResponse)
def get_my_work(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = MyWorkService(db=db, user=current_user)
    return service.get_my_work()