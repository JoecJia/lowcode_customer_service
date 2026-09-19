"""用户认证路由。

登录已整体切换为超星 passport Cookie 登录（见 routers/passport.py）。
原账号密码注册 / 登录接口（/api/register、/api/login）已下线。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dependencies.auth import get_current_user
from services.auth_service import get_user_by_id

router = APIRouter(prefix="/api")


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    avatar: str
    can_chat: int = 1
    can_admin: int = 0
    uid: Optional[str] = ""
    fid: Optional[str] = ""
    realname: Optional[str] = ""


class MeResponse(BaseModel):
    ok: bool
    user: Optional[UserResponse] = None


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(int(current_user["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return {"ok": True, "user": user}
