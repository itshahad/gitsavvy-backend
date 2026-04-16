from pydantic import BaseModel, ConfigDict


class BadgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    level: str
    icon: str