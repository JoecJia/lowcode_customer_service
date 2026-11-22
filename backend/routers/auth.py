import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from dependencies.auth import get_current_user
from services.auth_service import authenticate_user, get_user_by_id, register_user

router = APIRouter(prefix="/api")


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("请输入用户名")
        v = v.strip()
        if len(v) < 4:
            raise ValueError("用户名至少4位字符")
        if len(v) > 20:
            raise ValueError("用户名最多20位字符")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError("请输入密码")
        if len(v) < 8:
            raise ValueError("密码至少需要8位")
        if len(v) > 32:
            raise ValueError("密码最多32位")
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("密码需包含字母和数字")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    avatar: str
    can_chat: int = 1
    can_admin: int = 0


class RegisterResponse(BaseModel):
    ok: bool
    message: str
    data: Optional[dict] = None


class LoginResponse(BaseModel):
    ok: bool
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    user: Optional[UserResponse] = None


class MeResponse(BaseModel):
    ok: bool
    user: Optional[UserResponse] = None


@router.post("/register", status_code=201)
async def register(request: RegisterRequest):
    result = register_user(request.username, request.password)
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["detail"])
    return {
        "ok": True,
        "message": "注册成功",
        "data": {
            "user_id": result["user_id"],
            "username": result["username"],
        },
    }


@router.post("/login")
async def login(request: LoginRequest):
    if not request.username or not request.password:
        raise HTTPException(status_code=422, detail="请输入用户名和密码")
    result = authenticate_user(request.username, request.password)
    if not result["ok"]:
        raise HTTPException(status_code=401, detail=result["detail"])
    return result


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(int(current_user["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return {"ok": True, "user": user}
