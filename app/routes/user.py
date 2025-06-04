from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.user import UserLoginRequest, UserLoginResponse
from app.models.user import User
from app.db.database import get_db

router = APIRouter()

@router.post("/api/users/login", response_model=UserLoginResponse)
def login_user(payload: UserLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.wallet_address == payload.wallet_address).first()

    if not user:
        try:
            user = User(wallet_address=payload.wallet_address)
            db.add(user)
            db.commit()
            db.refresh(user)
        except:
            db.rollback()
            # 누군가 먼저 insert했을 가능성 → 다시 조회
            user = db.query(User).filter(User.wallet_address == payload.wallet_address).first()

    return UserLoginResponse(
        user_id=user.id,
        wallet_address=user.wallet_address,
        nickname=user.nickname
    )