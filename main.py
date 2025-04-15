from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import xrpl
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import EscrowCreate, EscrowFinish, Payment
from xrpl.utils import xrp_to_drops
from datetime import datetime
from os import urandom
from cryptoconditions import PreimageSha256
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from xrpl.models.requests import AccountObjects
import aiosqlite
import nest_asyncio 
nest_asyncio.apply()

client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
app = FastAPI()

# .env 파일 로드
load_dotenv()

# 환경변수 가져오기
PLATFORM_ADDRESS = os.getenv("PLATFORM_ADDRESS")
PLATFORM_SEED = os.getenv("PLATFORM_SEED")

class QuestionRequest(BaseModel):
    question: str
    reward_xrp: float
    questioner_seed: str

class AnswerRequest(BaseModel):
    question_id: int
    answer: str
    responder_address: str

class FinishRequest(BaseModel):
    question_id: int
    answer: str
    responder_address: str

def add_seconds(num):
    dt = datetime.now()
    return xrpl.utils.datetime_to_ripple_time(dt) + num

@app.post("/api/questions")
async def create_question_with_escrow(data: QuestionRequest):
    try:
        wallet = Wallet.from_seed(data.questioner_seed)

        # Step 1: 질문 DB 저장
        async with aiosqlite.connect("escrow.db") as db:
            cursor = await db.execute("""
                INSERT INTO questions (question, questioner_address)
                VALUES (?, ?)
            """, (data.question, wallet.address))
            await db.commit()
            question_id = cursor.lastrowid

        # Step 2: 에스크로 준비
        preimage = urandom(32)
        fulfillment = PreimageSha256(preimage=preimage)
        condition = fulfillment.condition_binary.hex().upper()
        fulfillment_hex = fulfillment.serialize_binary().hex().upper()

        cancel_after = add_seconds(7200)

        escrow_tx = EscrowCreate(
            account=wallet.address,
            destination=PLATFORM_ADDRESS,
            amount=xrp_to_drops(data.reward_xrp),
            condition=condition,
            cancel_after=cancel_after
        )

        # autofill + sign → sequence 포함
        signed_tx = xrpl.transaction.autofill_and_sign(escrow_tx, client, wallet)

        # signed_tx.transaction.sequence로 offer_sequence 확보
        offer_sequence = signed_tx.sequence

        # 네트워크에 제출
        response = xrpl.transaction.submit_and_wait(signed_tx, client)
        tx_hash = response.result.get("hash")

        print("Escrow 생성 완료!")
        print("Fulfillment 생성:", fulfillment_hex)
        print("Condition 생성:", condition)
        print("sequence 번호: ", offer_sequence)
        print()

        # Step 3: 에스크로 DB 저장
        async with aiosqlite.connect("escrow.db") as db:
            await db.execute("""
                INSERT INTO escrows (question_id, token, fulfillment, condition, offer_sequence, tx_hash, questioner_address)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                question_id,
                data.reward_xrp,
                fulfillment_hex,
                condition,
                offer_sequence,
                tx_hash,
                wallet.address
            ))
            await db.commit()
        
            print("Fulfillment 저장:", fulfillment_hex)
            print("Condition 저장:", condition)
            print("sequence 저장: ", offer_sequence)

        return {"message": "질문 등록 완료!", 
                "tx_hash": tx_hash, 
                "condition": condition, 
                "fulfillment": fulfillment_hex, 
                "question_id": question_id}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/answers")
async def submit_answer(data: AnswerRequest):
    async with aiosqlite.connect("escrow.db") as db:
        await db.execute("""
            INSERT INTO answers (question_id, answer, responder_address)
            VALUES (?, ?, ?)
        """, (data.question_id, data.answer, data.responder_address))
        await db.commit()
    return {"message": "답변 등록 완료!"}

@app.get("/api/answers")
async def get_answers(question_id: int):
    async with aiosqlite.connect("escrow.db") as db:
        cursor = await db.execute("SELECT answer, responder_address FROM answers WHERE question_id = ?", (question_id,))
        rows = await cursor.fetchall()
        return [{"answer": r[0], "responder_address": r[1]} for r in rows]

@app.post("/api/finish_escrow")
async def finish_escrow(data: FinishRequest):
    try:
        async with aiosqlite.connect("escrow.db") as db:
            cursor = await db.execute("SELECT token, fulfillment, condition, offer_sequence, questioner_address FROM escrows WHERE question_id = ?", (data.question_id,))
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다.")
            token, fulfillment_hex, condition_hex, offer_sequence, questioner_address = row

        print("Fulfillment 사용:", fulfillment_hex)
        print("Condition 사용:", condition_hex)
        print("sequence 사용: ", offer_sequence)
        print()

        platform_wallet = Wallet.from_seed(PLATFORM_SEED)
        escrow_finish_tx = xrpl.models.transactions.EscrowFinish(
            account=platform_wallet.address,
            owner=questioner_address,
            offer_sequence=offer_sequence,
            fulfillment=fulfillment_hex,
            condition=condition_hex
        )

        # Submit the transaction and report the results
        reply=""
        try:
            # 네트워크에 제출
            finish_response = xrpl.transaction.submit_and_wait(escrow_finish_tx, client, platform_wallet)

            tx_result = finish_response.result

        except xrpl.transaction.XRPLReliableSubmissionException as e:
            raise HTTPException(status_code=500, detail=f"Submit failed: {e}")

        print("Escrow 해제 완료!")

        payment_tx = xrpl.models.Payment(
            account=platform_wallet.address,
            destination=data.responder_address,
            amount=xrp_to_drops(token)
        )

        response = xrpl.transaction.submit_and_wait(payment_tx, client, platform_wallet)
        print("답변자에게 보상 완료:", response.result)

        return {
            "message": "에스크로 해제 및 보상 전송 완료!",
            "tx_result": {
                "escrow_tx": finish_response.result,
                "payment_tx": response.result
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def get_index():
    html_path = Path("static/index.html")
    return html_path.read_text(encoding="utf-8")
