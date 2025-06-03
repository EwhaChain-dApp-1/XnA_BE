# app/routes/questions.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.question import QuestionCreate
from app.models import question, tag, question_tag
from app.db.database import get_db

router = APIRouter(prefix="/questions", tags=["questions"])

@router.post("/")
def create_question(payload: QuestionCreate, db: Session = Depends(get_db)):
    q = question.Question(
        user_id=1,  # TODO: 실제 로그인 구현 시 교체
        title=payload.title,
        body=payload.body,
        reward_xrp=payload.reward_xrp
    )
    db.add(q)
    db.commit()
    db.refresh(q)

    for tag_name in payload.tags:
        tag_name = tag_name.strip().lstrip("#")
        t = db.query(tag.Tag).filter_by(name=tag_name).first()
        if not t:
            t = tag.Tag(name=tag_name)
            db.add(t)
            db.commit()
            db.refresh(t)
        qt = question_tag.QuestionTag(question_id=q.id, tag_id=t.id)
        db.add(qt)
    db.commit()

    return {"id": q.id, "message": "Question created"}
