# app/schemas/finishEscrow.py
from pydantic import BaseModel

class FinishEscrowRequest(BaseModel):
    question_id: int
    responder_address: str
    answer_id: int
