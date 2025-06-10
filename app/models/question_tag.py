from app.db.database import Base
from sqlalchemy import Column, ForeignKey, Integer

class QuestionTag(Base):
    __tablename__ = 'question_tags'

    question_id = Column(Integer, ForeignKey("questions.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)
