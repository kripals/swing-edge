from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.config import get_settings
from app.utils.auth import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    if body.password != settings.app_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    token = create_access_token()
    return TokenResponse(access_token=token)
