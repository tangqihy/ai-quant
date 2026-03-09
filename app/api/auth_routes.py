"""
鉴权相关 API：登录、验证 token。
不要求鉴权，供未登录用户获取 token。
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.services.auth_service import verify_password, create_token, verify_token

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    """验证密码，成功则返回 token。"""
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="密码错误")
    token = create_token()
    return {"success": True, "token": token}


@router.get("/verify")
async def verify(authorization: str | None = Header(None, alias="Authorization")):
    """
    验证当前 token 是否有效。
    请求头需带 Authorization: Bearer <token>；未带或无效返回 401。
    """
    token = _bearer_token(authorization)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="未登录或 token 已失效")
    return {"success": True, "valid": True}


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.strip().startswith("Bearer "):
        return None
    return authorization.strip()[7:].strip() or None
