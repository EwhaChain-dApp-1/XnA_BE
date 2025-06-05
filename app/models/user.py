# app/models/user.py
from sqlalchemy import Column, Integer, String, TIMESTAMP
from app.db.database import Base
from sqlalchemy.orm import relationship
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, unique=True, nullable=False)
    nickname = Column(String)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # 여기에 직접 문자열 참조 대신, 아래쪽에서 import된 Answer 클래스를 사용하거나, 문자열로 유지하되 `__init__` 이후에 relationship 설정
    answers = relationship("Answer", back_populates="user", lazy='joined')  # 문자열 사용
    questions = relationship("Question", back_populates="user", lazy='joined')  # 그대로 OK
