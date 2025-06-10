from fastapi import APIRouter
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/xaman", tags=["xaman"])

XUMM_API_KEY = os.getenv("XUMM_API_KEY")
XUMM_API_SECRET = os.getenv("XUMM_API_SECRET")
BASE_URL = "https://xumm.app/api/v1/platform"

headers = {
    "Content-Type": "application/json",
    "X-API-Key": XUMM_API_KEY,
    "X-API-Secret": XUMM_API_SECRET,
}

@router.post("/connect")
async def create_payload():
    payload = {
        "txjson": {
            "TransactionType": "SignIn"
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/payload", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return {
            "uuid": data["uuid"],
            "qr": data["refs"]["qr_png"],
            "next": data["next"]["always"]
        }
    

@router.get("/status/{uuid}")
async def get_payload_status(uuid: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/payload/{uuid}", headers=headers)
        response.raise_for_status()
        return response.json()