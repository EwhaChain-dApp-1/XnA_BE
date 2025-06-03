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

    # 관계 정의
    questions = relationship("Question", back_populates="user")
