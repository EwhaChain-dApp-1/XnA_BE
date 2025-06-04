# app/routes/questions.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.question import QuestionCreate
from app.models import question, tag, question_tag
from app.db.database import get_db

from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import EscrowCreate
from xrpl.transaction import autofill_and_sign, submit_and_wait
from xrpl.utils import xrp_to_drops, datetime_to_ripple_time
from os import urandom
from cryptoconditions import PreimageSha256
from xrpl.utils import datetime_to_ripple_time
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from app.models.question import Question
from app.schemas.questionList import QuestionListResponse

load_dotenv()
PLATFORM_ADDRESS = os.getenv("PLATFORM_ADDRESS")
PLATFORM_SEED = os.getenv("PLATFORM_SEED")
client = JsonRpcClient("https://s.altnet.rippletest.net:51234")

router = APIRouter(prefix="/questions", tags=["questions"])

@router.get("/", response_model=list[QuestionListResponse])
def list_questions(db: Session = Depends(get_db)):
    questions = db.query(Question).order_by(Question.created_at.desc()).all()
    return questions

def add_seconds(days=0, seconds=0):
    dt = datetime.utcnow() + timedelta(days=days, seconds=seconds)
    return datetime_to_ripple_time(dt)

@router.post("/")
def create_question(payload: QuestionCreate, db: Session = Depends(get_db)):
    try:
        # 🌐 질문자 지갑
        user = db.query(question.User).filter_by(id=payload.user_id).first()
        if not user or not user.wallet_address:
            raise HTTPException(status_code=400, detail="Invalid user")

        questioner_wallet = Wallet(seed=payload.questioner_seed, sequence=0)

        # 🎯 1. DB에 질문 등록
        q = question.Question(
            user_id=user.id,
            title=payload.title,
            body=payload.body,
            reward_xrp=payload.reward_xrp
        )
        db.add(q)
        db.commit()
        db.refresh(q)

        # 🎯 2. 태그 처리
        for tag_name in payload.tags:
            tag_name = tag_name.strip().lstrip("#")
            t = db.query(tag.Tag).filter_by(name=tag_name).first()
            if not t:
                t = tag.Tag(name=tag_name)
                db.add(t)
                db.commit()
                db.refresh(t)
            db.add(question_tag.QuestionTag(question_id=q.id, tag_id=t.id))
        db.commit()

        # 🎯 3. 에스크로 트랜잭션 생성
        preimage = urandom(32)
        fulfillment = PreimageSha256(preimage=preimage)
        condition = fulfillment.condition_binary.hex().upper()
        fulfillment_hex = fulfillment.serialize_binary().hex().upper()

        cancel_after = add_seconds(days=7)

        escrow_tx = EscrowCreate(
            account=questioner_wallet.address,
            destination=PLATFORM_ADDRESS,
            amount=xrp_to_drops(payload.reward_xrp),
            condition=condition,
            cancel_after=cancel_after
        )

        signed_tx = autofill_and_sign(escrow_tx, client, questioner_wallet)
        response = submit_and_wait(signed_tx, client)

        if not response.is_successful():
            raise HTTPException(status_code=500, detail="Escrow submission failed")

        # 🎯 4. DB에 fulfillment 등 정보 저장
        q.fulfillment = fulfillment_hex
        q.condition = condition
        q.tx_hash = response.result.get("hash")
        db.commit()

        return {
            "id": q.id,
            "tx_hash": q.tx_hash,
            "condition": q.condition,
            "fulfillment": q.fulfillment,
            "message": "질문 등록 및 에스크로 완료"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{question_id}")
def get_question_detail(question_id: int, db: Session = Depends(get_db)):
    # 질문 정보 조회
    q = db.query(question.Question).filter(question.Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    # 태그 조회
    tag_names = (
        db.query(tag.Tag.name)
        .join(question_tag.QuestionTag, question_tag.QuestionTag.tag_id == tag.Tag.id)
        .filter(question_tag.QuestionTag.question_id == q.id)
        .all()
    )

    return {
        "id": q.id,
        "title": q.title,
        "body": q.body,
        "reward_xrp": float(q.reward_xrp),
        "created_at": q.created_at.isoformat(),
        "wallet_address": q.user.wallet_address,  # 관계로부터 user 지갑 주소 추출
        "tags": [t[0] for t in tag_names],
    }