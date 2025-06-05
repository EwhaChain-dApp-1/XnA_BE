from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, BigInteger
from sqlalchemy.orm import relationship
from app.db.database import Base

class Escrow(Base):
    __tablename__ = "escrows"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    token = Column(Numeric(16, 6), nullable=False)
    tx_hash = Column(String, nullable=False, unique=True)
    fulfillment = Column(String, nullable=False)
    condition = Column(String, nullable=False)
    cancel_after = Column(Integer, nullable=False)
    offer_sequence = Column(Integer, nullable=False)

    question = relationship("Question", back_populates="escrow")