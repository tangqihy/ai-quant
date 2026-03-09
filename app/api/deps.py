"""
API 依赖：鉴权等。
"""
from fastapi import Header, HTTPException, Depends

from app.services.auth_service import verify_token


def require_auth(authorization: str | None = Header(None, alias="Authorization")):
    """
    从 Authorization: Bearer <token> 中取出 token 并校验。
    未带或无效时抛出 401，保护 /api/* 下除 /api/auth/* 外的所有接口。
    """
    token = _bearer_token(authorization)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="未登录或 token 已失效")
    return token


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.strip().startswith("Bearer "):
        return None
    return authorization.strip()[7:].strip() or None
