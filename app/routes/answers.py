from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.answer import Answer
from app.schemas.answer import AnswerCreate
from app.schemas.finishEscrow import FinishEscrowRequest
from app.db.database import get_db
from app.models.question import Question
from app.models.user import User
from app.models.escrow import Escrow


import aiosqlite
import xrpl
from xrpl.wallet import Wallet
from xrpl.models.transactions import EscrowFinish, Payment
from xrpl.transaction import submit_and_wait, XRPLReliableSubmissionException
from xrpl.clients import JsonRpcClient
from xrpl.utils import xrp_to_drops
import nest_asyncio 
nest_asyncio.apply()

import os

router = APIRouter(prefix="/answers", tags=["answers"])

PLATFORM_SEED = os.getenv("PLATFORM_SEED")
client = JsonRpcClient("https://s.altnet.rippletest.net:51234")  # Testnet 기준

@router.post("/")
def create_answer(payload: AnswerCreate, db: Session = Depends(get_db)):
    answer = Answer(
        question_id=payload.question_id,
        user_id=payload.user_id,
        body=payload.body
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    # ✅ 작성자 지갑 주소 조회
    user = db.query(User).filter(User.id == answer.user_id).first()

    return {
        "id": answer.id,
        "question_id": answer.question_id,
        "user_id": answer.user_id,
        "wallet_address": user.wallet_address if user else None,  # ✅ 지갑 주소 포함
        "body": answer.body,
        "created_at": answer.created_at.isoformat(),
        "is_accepted": answer.is_accepted,
        "message": "Answer created"
    }


@router.post("/finish_escrow")
async def finish_escrow(data: FinishEscrowRequest, db: Session = Depends(get_db)):
    try:
        # 1. DB에서 에스크로 정보 조회 (escrows 테이블만)
        escrow = db.query(Escrow).filter(Escrow.question_id == data.question_id).first()
        if not escrow:
            raise HTTPException(status_code=404, detail="에스크로 정보가 없습니다.")

        token = escrow.token
        fulfillment_hex = escrow.fulfillment
        condition_hex = escrow.condition
        offer_sequence = escrow.offer_sequence

        # ✅ owner 값은 질문자가 아니라 플랫폼 A 주소!
        platform_a_address = "rE8PP6RHQnipSc7wTNjEXhx6p5vfGaQsJR"
        platform_b_wallet = Wallet.from_seed("sEdT6DSMpTqB5WW4WEHwBAojaCvKKFo")  # 플랫폼 B

        print("✅ 1번까지 완료")
        print("✅ 질문 ID:", data.question_id)
        print("✅ 답변자 주소:", data.responder_address)
        print("✅ Escrow 생성자(owner):", platform_a_address)
        print("✅ Escrow 시퀀스:", offer_sequence)
        print("✅ Fulfillment:", fulfillment_hex)
        print("✅ Condition:", condition_hex)
        print("✅ 전송 금액 (XRP):", token)

        # 2. SQLAlchemy를 사용해 질문자 주소 조회 (users 테이블을 통해)
        question_obj = db.query(Question).filter(Question.id == data.question_id).first()
        if not question_obj:
            raise HTTPException(status_code=404, detail="질문이 존재하지 않습니다.")
        
        if question_obj.is_reward_sent:
            raise HTTPException(status_code=400, detail="이미 보상이 완료된 질문입니다.")
        
        questioner_address = question_obj.user.wallet_address
        if not questioner_address:
            raise HTTPException(status_code=400, detail="질문자의 지갑 주소가 없습니다.")

        # ✅ 3. EscrowFinish 트랜잭션
        escrow_finish_tx =  xrpl.models.transactions.EscrowFinish(
            account=platform_b_wallet.address,     # 플랫폼 B
            owner=platform_a_address,                      # Escrow 생성한 플랫폼 A
            offer_sequence=offer_sequence,
            fulfillment=fulfillment_hex,
            condition=condition_hex
        )

        print("✅ 트랜잭션 구성 완료")

        finish_response =  xrpl.transaction.submit_and_wait(escrow_finish_tx, client, platform_b_wallet)
        print("✅ Escrow 해제 완료")

        # 3. Payment 트랜잭션: 답변자에게 보상 전송
        payment_tx = xrpl.models.Payment(
            account=platform_b_wallet.classic_address,
            destination=data.responder_address,
            amount=xrp_to_drops(token)
        )

        payment_response = xrpl.transaction.submit_and_wait(payment_tx, client, platform_b_wallet)
        print("✅ 보상 전송 완료")

        # 4. DB 상태 업데이트
        # 4-1. 질문 상태 업데이트
        question_obj.is_reward_sent = True

        # 4-2. 답변 상태 업데이트
        accepted_answer = db.query(Answer).filter(
            Answer.id == data.answer_id,
            Answer.question_id == data.question_id
        ).first()

        if not accepted_answer:
            raise HTTPException(status_code=404, detail="채택된 답변을 찾을 수 없습니다.")

        accepted_answer.is_accepted = True

        # 4-3. 커밋
        db.commit()

        return {
            "message": "에스크로 해제 및 보상 전송 완료!",
            "tx_result": {
                "escrow_tx": finish_response.result,
                "payment_tx": payment_response.result
            }
        }

    except XRPLReliableSubmissionException as e:
        raise HTTPException(status_code=500, detail=f"XRPL 제출 실패: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


