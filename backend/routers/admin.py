"""管理后台 API 路由：Agent 配置 + 账号管理"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
import re

from dependencies.auth import require_admin
from services.agent_config_service import get_file_content, get_file_tree
from services.admin_service import (
    create_account,
    list_accounts,
    update_password,
    update_permissions,
)

router = APIRouter(prefix="/api/admin")


# ====== Agent 配置 ======

@router.get("/agent-config/tree")
async def agent_config_tree(admin: dict = Depends(require_admin)):
    tree = get_file_tree()
    return {"ok": True, "data": {"tree": tree}}


@router.get("/agent-config/file")
async def agent_config_file(
    path: str = Query(...),
    admin: dict = Depends(require_admin),
):
    content = get_file_content(path)
    if content is None:
        raise HTTPException(status_code=404, detail="文件不存在或不可预览")
    return {"ok": True, "data": {"path": path, "content": content}}


# ====== 账号管理 ======

@router.get("/accounts")
async def get_accounts(
    search: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    users, total = list_accounts(search=search, offset=offset, limit=limit)
    return {
        "ok": True,
        "data": {
            "users": users,
            "total": total,
            "offset": offset,
            "limit": limit,
        },
    }


class CreateAccountRequest(BaseModel):
    username: str
    password: str
    can_chat: int = 1
    can_admin: int = 0


@router.post("/accounts", status_code=201)
async def add_account(
    body: CreateAccountRequest,
    admin: dict = Depends(require_admin),
):
    result = create_account(
        body.username,
        body.password,
        body.can_chat,
        body.can_admin,
    )
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["detail"])
    return {
        "ok": True,
        "message": "账号添加成功",
        "data": {
            "user_id": result["user_id"],
            "username": result["username"],
        },
    }


class UpdatePasswordRequest(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError("请输入新密码")
        if len(v) < 8:
            raise ValueError("密码至少需要8位")
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("密码需包含字母和数字")
        return v


@router.patch("/accounts/{user_id}/password")
async def change_password(
    user_id: int,
    body: UpdatePasswordRequest,
    admin: dict = Depends(require_admin),
):
    result = update_password(user_id, body.password)
    if not result["ok"]:
        raise HTTPException(status_code=422, detail=result["detail"])
    return {"ok": True, "message": "密码修改成功"}


class UpdatePermissionsRequest(BaseModel):
    can_chat: int
    can_admin: int


@router.patch("/accounts/{user_id}/permissions")
async def change_permissions(
    user_id: int,
    body: UpdatePermissionsRequest,
    admin: dict = Depends(require_admin),
):
    # 获取用户名用于判断 admin 保护
    import sqlite3
    from config import DB_PATH
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")

    result = update_permissions(user_id, body.can_chat, body.can_admin, row["username"])
    if not result["ok"]:
        raise HTTPException(status_code=403, detail=result["detail"])
    return {"ok": True, "message": "权限修改成功"}
