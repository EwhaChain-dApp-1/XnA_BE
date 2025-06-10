from pydantic import BaseModel

class UserLoginRequest(BaseModel):
    wallet_address: str

class UserLoginResponse(BaseModel):
    user_id: int
    wallet_address: str
    nickname: str | None = None