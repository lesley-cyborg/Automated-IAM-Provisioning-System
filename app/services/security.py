import hmac
import hashlib
import time
from typing import Optional
from fastapi import Depends, HTTPException, Request, Header
from jose import jwt, JWTError
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    HR_WEBHOOK_SECRET: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


sec = SecuritySettings()


def verify_hmac(raw_body: bytes, signature: Optional[str]) -> bool:
    """Constant-time HMAC-SHA256 check of the raw request body."""
    if not signature:
        return False
    expected = hmac.new(
        sec.HR_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    # accept either "sha256=<hex>" or bare "<hex>"
    provided = signature.split("=")[-1]
    return hmac.compare_digest(expected, provided)


def create_access_token(role: str, sub: str, expires_in: int = 3600) -> str:
    payload = {"sub": sub, "role": role, "exp": int(time.time()) + expires_in}
    return jwt.encode(payload, sec.JWT_SECRET, algorithm=sec.JWT_ALGORITHM)


async def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, sec.JWT_SECRET, algorithms=[sec.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")
    return payload  # {"sub":..., "role":...}


def require_role(required: str):
    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") != required:
            raise HTTPException(403, f"Requires role '{required}'")
        return user
    return _dep