# app/models/question.py

from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime
from app.models.user import User  # 반드시 직접 import

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    reward_xrp = Column(Numeric(16, 6), nullable=False)
    is_reward_sent = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # 관계 정의
    user = relationship("User", back_populates="questions")
    answers = relationship("Answer", back_populates="question")  # 문자열 사용
    escrow = relationship("Escrow", back_populates="question", uselist=False)
