"""超星 Passport Cookie 登录路由。

``POST /api/passport/cookie/login``
- 带有效 Bearer 且 Cookie 未被篡改 → 走快路径（0 次外部调用）
- 否则读 Cookie 四要素验签 → 补姓名 → 落库 → 签发 1 天本地 JWT

返回值结构与原 ``/api/login`` 保持一致，前端解析逻辑无需改动。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.auth_service import create_token, decode_token
from services.passport_login_service import get_user_login_info

router = APIRouter(prefix="/api/passport")

# auto_error=False：未带 token 时静默走 passport 校验，而不是直接 401
_optional_bearer = HTTPBearer(auto_error=False)


@router.post("/cookie/login")
async def passport_cookie_login(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
):
    payload: Optional[dict] = None
    if credentials and credentials.credentials:
        try:
            payload = decode_token(credentials.credentials)
        except Exception:  # noqa: BLE001
            payload = None

    user = await get_user_login_info(request, payload)
    if not user:
        raise HTTPException(status_code=401, detail="用户未登录")

    token = create_token(
        user["id"],
        user["username"],
        user["role"],
        user["can_chat"],
        user["can_admin"],
        uid=user.get("uid"),
        fid=user.get("fid"),
    )
    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }
