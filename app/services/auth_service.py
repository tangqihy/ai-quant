"""
鉴权服务：密码校验、Token 生成与验证。
密码从环境变量 QUANT_AUTH_PASSWORD 读取；未配置时任何人无法登录。
"""
import os
import secrets
import time
from typing import Optional

# 内存中有效 token -> 过期时间戳（简单实现，进程内有效）
_valid_tokens: dict[str, float] = {}
_TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 天


def _get_password() -> Optional[str]:
    return os.environ.get("QUANT_AUTH_PASSWORD") or None


def verify_password(password: str) -> bool:
    """校验密码是否与环境变量中的一致。"""
    expected = _get_password()
    if not expected:
        return False
    return secrets.compare_digest(password.strip(), expected)


def create_token() -> str:
    """生成新 token 并加入有效集合。"""
    token = secrets.token_urlsafe(32)
    _valid_tokens[token] = time.time() + _TOKEN_TTL_SECONDS
    return token


def verify_token(token: str) -> bool:
    """验证 token 是否有效（存在且未过期）。"""
    if not token or not token.strip():
        return False
    exp = _valid_tokens.get(token.strip())
    if exp is None:
        return False
    if time.time() > exp:
        _valid_tokens.pop(token.strip(), None)
        return False
    return True


def revoke_token(token: str) -> None:
    """使 token 失效（可选，用于登出）。"""
    _valid_tokens.pop(token.strip(), None)


# 导出 TTL 常量供测试或配置使用
TOKEN_TTL_SECONDS = _TOKEN_TTL_SECONDS
