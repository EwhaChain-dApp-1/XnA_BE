# app/routes/questions.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models import question, tag, question_tag, escrow
from app.db.database import get_db
from typing import List
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.utils import xrp_to_drops, datetime_to_ripple_time
from cryptoconditions import PreimageSha256
from os import urandom
from cryptoconditions import PreimageSha256
from datetime import datetime, timedelta
import os
import xumm
import xrpl
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import EscrowCreate, EscrowFinish, Payment
from dotenv import load_dotenv
from app.models.answer import Answer
from app.models.escrow import Escrow
from app.schemas.questionList import QuestionListResponse
from app.models.question import Question
from app.schemas.question_signed import QuestionCreateSigned
import requests


load_dotenv()
PLATFORM_ADDRESS = os.getenv("PLATFORM_ADDRESS")
PLATFORM_SEED = os.getenv("PLATFORM_SEED")
client = JsonRpcClient("https://s.altnet.rippletest.net:51234")

xumm_api_key = os.getenv("XUMM_API_KEY")
xumm_api_secret = os.getenv("XUMM_API_SECRET")
sdk = xumm.XummSdk(xumm_api_key, xumm_api_secret)

router = APIRouter(prefix="/questions", tags=["questions"])


def add_seconds(days=0, seconds=0):
    dt = datetime.utcnow() + timedelta(days=days, seconds=seconds)
    return datetime_to_ripple_time(dt)


@router.get("", response_model=list[QuestionListResponse])
def list_questions(db: Session = Depends(get_db)):
    questions = db.query(Question).order_by(Question.created_at.desc()).all()
    return questions


@router.get("/{question_id}/answers")
def get_answers_by_question_id(question_id: int, db: Session = Depends(get_db)):
    answers = (
        db.query(Answer)
        .filter(Answer.question_id == question_id)
        .order_by(Answer.created_at.desc())
        .all()
    )

    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "question_id": a.question_id,
            "body": a.body,
            "created_at": a.created_at.isoformat(),
            "is_accepted": a.is_accepted,
            "wallet_address": a.user.wallet_address if a.user else None  # ✅ 핵심
        }
        for a in answers
    ]



@router.get("/recent", response_model=List[QuestionListResponse])
def get_recent_questions(db: Session = Depends(get_db)):
    questions = (
        db.query(question.Question)
        .order_by(question.Question.created_at.desc())
        .limit(3)
        .all()
    )
    return questions


# @router.get("/escrow/precondition")
# def create_escrow_condition():
#     preimage = urandom(32)
#     fulfillment = PreimageSha256(preimage=preimage)
#     condition = fulfillment.condition_binary.hex().upper()
#     fulfillment_hex = fulfillment.serialize_binary().hex().upper()
#     return {
#         "preimage": preimage.hex().upper(),
#         "fulfillment": fulfillment_hex,
#         "condition": condition
#     }


@router.post("/xumm/create-payload")
def create_xumm_payload(request_data: dict):
    """
    XUMM SDK를 사용하여 Payload 생성
    """
    try:
        # 디버깅 로그 추가
        print("Request Data:", request_data)

        # XUMM SDK를 사용하여 Payload 생성
        payload = sdk.payload.create(request_data)

        # 생성된 Payload 반환
        print("Payload Created:", payload.to_dict())
        return payload.to_dict()

    except Exception as e:
        print("Internal Server Error:", str(e))
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.get("/xumm/get-payload/{uuid}")
def get_xumm_payload(uuid: str):
    """
    XUMM SDK를 사용하여 Payload 상태 조회
    """
    try:
        # Payload 상태 조회
        payload = sdk.payload.get(uuid)

        # 조회된 Payload 반환
        return payload.to_dict()

    except Exception as e:
        print("Internal Server Error:", str(e))
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")



@router.post("")
def create_question(payload: QuestionCreateSigned, db: Session = Depends(get_db)):
    try:
        # print("✅ create_question 진입, payload:", payload.dict())

        # 1. 사용자 확인
        user = db.query(question.User).filter_by(id=payload.user_id).first()
        if not user or not user.wallet_address:
            raise HTTPException(status_code=400, detail="Invalid user")

        # 2. 질문 저장
        q = question.Question(
            user_id=user.id,
            title=payload.title,
            body=payload.body,
            reward_xrp=payload.reward_xrp
        )
        db.add(q)
        db.commit()
        db.refresh(q)

        # 3. 태그 처리
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

        preimage = urandom(32)
        fulfillment = PreimageSha256(preimage=preimage)
        condition = fulfillment.condition_binary.hex().upper()
        fulfillment_hex = fulfillment.serialize_binary().hex().upper()
        cancel_after = add_seconds(days=30)

        wallet = Wallet.from_seed("sEdTxWmBUk2dpSHrXtADwHxTvDBKiyE")

        escrow_tx = EscrowCreate(
            account=wallet.address,
            destination="rfiA1zTWa6i7oupfNxQdzyeTWEXfggj3gk",
            amount=xrp_to_drops(payload.reward_xrp),
            condition=condition,
            cancel_after=cancel_after
        )
        

        # autofill + sign → sequence 포함
        signed_tx = xrpl.transaction.autofill_and_sign(escrow_tx, client, wallet)

        # signed_tx.transaction.sequence로 offer_sequence 확보
        offer_sequence = signed_tx.sequence

        # 네트워크에 제출
        response = xrpl.transaction.submit_and_wait(signed_tx, client)
        # print("🚀 submit_and_wait 결과:", response.result)
        tx_hash = response.result.get("hash")

        print("Escrow 생성 완료!")
        print("Fulfillment 생성:", fulfillment_hex)
        print("Condition 생성:", condition)
        print("sequence 번호: ", offer_sequence)
        print()

        # 4. 에스크로 저장
        escrow = Escrow(
            question_id=q.id,
            token=payload.reward_xrp,
            tx_hash=tx_hash,
            fulfillment=fulfillment_hex,
            condition=condition,
            cancel_after=cancel_after,
            offer_sequence=offer_sequence
        )
        db.add(escrow)
        db.commit()

        return {
            "id": q.id,
            "tx_hash": escrow.tx_hash,
            "condition": escrow.condition,
            "fulfillment": escrow.fulfillment,
            "message": "질문 및 에스크로 등록 완료"
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
        "user_id": q.user_id,
        "tags": [t[0] for t in tag_names],
        "is_reward_sent": q.is_reward_sent,
    }