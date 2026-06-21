from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.auth_service import decode_token

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="无效的认证令牌")
    # Ensure can_chat/can_admin are present with defaults for legacy tokens
    payload.setdefault("can_chat", 1)
    payload.setdefault("can_admin", 0)
    return payload


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin" or current_user.get("can_admin") != 1:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user
