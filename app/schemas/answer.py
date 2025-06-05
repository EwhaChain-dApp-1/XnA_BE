from pydantic import BaseModel

class AnswerCreate(BaseModel):
    question_id: int
    user_id: int
    body: str
