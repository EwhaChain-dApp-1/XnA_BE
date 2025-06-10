# app/schemas/question.py

from pydantic import BaseModel
from datetime import datetime

class QuestionListResponse(BaseModel):
    id: int
    title: str
    reward_xrp: float
    created_at: datetime
    user_id: int

    class Config:
        orm_mode = True
