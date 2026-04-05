"""
JWT auth — single-user app.
Login with APP_PASSWORD → receive a JWT → attach to all API calls as Bearer token.

No user table needed. The password is in .env. Token is stateless.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()

_bearer = HTTPBearer(auto_error=True)

_SUBJECT = "swingdge-user"


def create_access_token() -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": _SUBJECT,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        subject: str = payload.get("sub", "")
        if subject != _SUBJECT:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return subject
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def verify_trigger_secret(authorization: str | None) -> None:
    """
    Validates the TRIGGER_SECRET header from GitHub Actions cron requests.
    Expected header: Authorization: Bearer <TRIGGER_SECRET>
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization format")
    if parts[1] != settings.trigger_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid trigger secret")
