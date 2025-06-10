from pydantic import BaseModel
from typing import List

class Question(BaseModel):
    user_id: int
    title: str
    body: str
    reward_xrp: float
    tags: List[str]
