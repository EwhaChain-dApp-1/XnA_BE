from pydantic import BaseModel
from typing import List


class QuestionCreateSigned(BaseModel):
    user_id: int
    title: str
    body: str
    reward_xrp: float
    tags: List[str]

    # XRPL escrow 관련 추가 필드
    tx_hash: str