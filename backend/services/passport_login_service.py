"""Passport Cookie 登录编排。

对应 Java 参考实现 ``LoginService.getUserLoginInfo(request, response)``：

1. 快路径：本地 JWT 有效，且 Cookie 中的 UID/fid 与 JWT 一致（未被篡改）→ 直接返回
2. 否则走完整校验：Cookie 四要素验签 → 本地缓存 → 补真实姓名 → 落库 upsert

与参考实现的差异（均为有意为之）：
- 本地 token 走 ``Authorization: Bearer``，不写 ``token`` Cookie
- 用户身份键为 ``uid``（参考实现同样如此），``fid`` 仅作记录与缓存 key
"""

from __future__ import annotations

import sys
import time
from typing import Any, Optional

from fastapi import Request

from config import DEBUG
from services.auth_service import get_user_by_id, upsert_passport_user
from services.cookie_service import verify_passport_cookie, verify_passport_cookie_changed
from services.passport_service import get_passport_user_info

# 缓存 key 前缀（对齐 Java：CACHE_KEY_LOGIN_VO = "login_info:"）
CACHE_KEY_LOGIN_VO = "login_info:"
# 用户信息缓存时长：本地 JWT 已覆盖绝大多数请求，这里只用于减少重复打 passport
LOGIN_INFO_CACHE_TTL_SECONDS = 30 * 60

# 内存缓存：key -> (value, expires_at)
_cache: dict[str, tuple[Any, float]] = {}


def _debug(*args: Any) -> None:
    if DEBUG:
        print("[passport-login]", *args, file=sys.stderr)


def _cache_get(key: str) -> Any | None:
    item = _cache.get(key)
    if not item:
        return None
    value, expires_at = item
    if expires_at <= time.time():
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any, ttl: float) -> None:
    _cache[key] = (value, time.time() + ttl)


def clear_cache() -> None:
    _cache.clear()


def _client_ip(request: Request) -> Optional[str]:
    """取真实客户端 IP（用于按官方文档要求透传给 passport）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else None


async def get_user_login_info(request: Request, token_payload: Optional[dict] = None) -> Optional[dict]:
    """获取当前登录用户；未登录返回 None。"""
    # ── 1. 快路径：本地 JWT 有效且 Cookie 未被篡改 ──
    if token_payload:
        native_uid = str(token_payload.get("uid") or "")
        native_fid = str(token_payload.get("fid") or "")
        user_id = token_payload.get("sub")
        if user_id and native_uid and not verify_passport_cookie_changed(native_uid, native_fid, request):
            user = get_user_by_id(int(user_id))
            if user:
                return user
            _debug("JWT 中的用户已不存在，回退到完整校验")

    # ── 2. 完整校验 ──
    return await process_user_info(request)


async def process_user_info(request: Request) -> Optional[dict]:
    """Cookie 验签 → 补姓名 → 落库，返回本地用户字典。"""
    verified = await verify_passport_cookie(request)
    if not verified:
        _debug("无法从 Cookie 获取有效的用户登录信息")
        return None

    uid, fid = verified["uid"], verified["fid"]
    cache_key = f"{CACHE_KEY_LOGIN_VO}{fid}:{uid}"

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # 补真实姓名：失败只记日志，不阻断登录
    info = await get_passport_user_info(
        uid,
        client_ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    realname = (info or {}).get("realname") or ""
    if not realname:
        _debug("未获取到真实姓名，uid=", uid)

    user = upsert_passport_user(uid, fid, realname)
    if user:
        _cache_set(cache_key, user, LOGIN_INFO_CACHE_TTL_SECONDS)
        _debug("登录成功并已缓存: uid=", uid, "fid=", fid, "id=", user["id"])
    return user
