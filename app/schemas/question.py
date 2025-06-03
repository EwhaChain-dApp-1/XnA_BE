# app/schemas/question.py
from pydantic import BaseModel
from typing import List

class QuestionCreate(BaseModel):
    title: str
    body: str
    reward_xrp: float
    tags: List[str]
