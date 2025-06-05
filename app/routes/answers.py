from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.answer import Answer
from app.schemas.answer import AnswerCreate
from app.schemas.finishEscrow import FinishEscrowRequest
from app.db.database import get_db
from app.schemas.question import Question


import aiosqlite
import xrpl
from xrpl.wallet import Wallet
from xrpl.models.transactions import EscrowFinish, Payment
from xrpl.transaction import submit_and_wait, XRPLReliableSubmissionException
from xrpl.clients import JsonRpcClient
from xrpl.utils import xrp_to_drops

import os

router = APIRouter(prefix="/answers", tags=["answers"])

PLATFORM_SEED = os.getenv("PLATFORM_SEED")
client = JsonRpcClient("https://s.altnet.rippletest.net:51233")  # Testnet 기준

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
    return {"id": answer.id, "message": "Answer created"}


@router.post("/finish_escrow")
async def finish_escrow(data: FinishEscrowRequest, db: Session = Depends(get_db)):
    try:
        # 1. DB에서 에스크로 정보 조회 (escrows 테이블만)
        async with aiosqlite.connect("escrow.db") as dbfile:
            cursor = await dbfile.execute(
                "SELECT token, fulfillment, condition, offer_sequence FROM escrows WHERE question_id = ?",
                (data.question_id,)
            )
            row = await cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="에스크로 정보가 없습니다.")
            
            token, fulfillment_hex, condition_hex, offer_sequence = row

        # 2. SQLAlchemy를 사용해 질문자 주소 조회 (users 테이블을 통해)
        question_obj = db.query(Question).filter(Question.id == data.question_id).first()
        if not question_obj:
            raise HTTPException(status_code=404, detail="질문이 존재하지 않습니다.")
        
        questioner_address = question_obj.user.wallet_address
        if not questioner_address:
            raise HTTPException(status_code=400, detail="질문자의 지갑 주소가 없습니다.")

        # 2. EscrowFinish 트랜잭션 생성 및 제출
        platform_wallet = Wallet.from_seed(PLATFORM_SEED)

        escrow_finish_tx = EscrowFinish(
            account=platform_wallet.classic_address,
            owner=questioner_address,
            offer_sequence=offer_sequence,
            fulfillment=fulfillment_hex,
            condition=condition_hex
        )

        finish_response = submit_and_wait(escrow_finish_tx, client, platform_wallet)
        print("✅ Escrow 해제 결과:", finish_response.result)

        # 3. Payment 트랜잭션: 답변자에게 보상 전송
        payment_tx = Payment(
            account=platform_wallet.classic_address,
            destination=data.responder_address,
            amount=xrp_to_drops(token)
        )

        payment_response = submit_and_wait(payment_tx, client, platform_wallet)
        print("✅ 보상 전송 완료:", payment_response.result)

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


