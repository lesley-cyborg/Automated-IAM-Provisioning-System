from fastapi import APIRouter
from pydantic import BaseModel
from ..services.security import create_access_token

router = APIRouter()
# PRODUCTION NOTE: replace with real IdP (Keycloak/Okta/Auth0). This is a mock.
USERS = {"admin": {"password": "admin123", "role": "admin"},
         "viewer": {"password": "viewer123", "role": "viewer"}}

class LoginReq(BaseModel):
    username: str
    password: str

@router.post("/auth/token")
async def login(req: LoginReq):
    u = USERS.get(req.username)
    if not u or u["password"] != req.password:
        return {"error": "invalid_credentials"}
    return {"access_token": create_access_token(u["role"], req.username),
            "token_type": "bearer", "role": u["role"]}