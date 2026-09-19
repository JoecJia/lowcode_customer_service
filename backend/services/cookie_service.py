"""Passport Cookie 解析与校验。

对齐 Java 参考实现 ``CookieService``：

- ``verify_passport_cookie``：直接取 Cookie **原始值**（不做 URL 解码）后调用验签
- ``verify_passport_cookie_changed``：用 **URL 解码后**的值与本地 JWT 中的 uid/fid 比较（忽略大小写）

Cookie 四要素名称大小写敏感：``UID`` / ``fid`` / ``vc3`` / ``_d``。
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request

from services.passport_crypto import decode_url
from services.passport_service import is_login_passport

COOKIE_NAME_UID = "UID"
COOKIE_NAME_FID = "fid"
COOKIE_NAME_VC3 = "vc3"
COOKIE_NAME_TIME = "_d"


def _raw(request: Request, name: str) -> str:
    """取 Cookie 原始值（与 Java ``cookie.getValue()`` 等价，不做 URL 解码）。"""
    try:
        return request.cookies.get(name, "") or ""
    except Exception:  # noqa: BLE001
        return ""


def _decoded(request: Request, name: str) -> str:
    """取 URL 解码后的 Cookie 值（与 Java ``CookieUtils.getString`` 等价）。"""
    return decode_url(_raw(request, name))


async def verify_passport_cookie(request: Request) -> Optional[dict]:
    """校验 Passport Cookie 登录态。

    :return: 验签通过返回 ``{"uid": str, "fid": str}``，否则返回 None
    """
    uid = _raw(request, COOKIE_NAME_UID)
    fid = _raw(request, COOKIE_NAME_FID)
    vc3 = _raw(request, COOKIE_NAME_VC3)
    login_time = _raw(request, COOKIE_NAME_TIME)

    if not await is_login_passport(uid, vc3, login_time):
        return None

    try:
        uid_text = str(int(uid))
    except (TypeError, ValueError):
        return None

    return {"uid": uid_text, "fid": (fid or "").strip()}


def verify_passport_cookie_changed(native_uid: str, native_fid: str, request: Request) -> bool:
    """比较本地 JWT 中的 uid/fid 与当前 Passport Cookie 是否一致。

    任一非空且不相等即视为「已变化」（Cookie 被改写 / 用户切换了账号）。
    请求无 Cookie 时返回 False（视为未变化，交由后续流程处理）。
    """
    passport_uid = _decoded(request, COOKIE_NAME_UID)
    passport_fid = _decoded(request, COOKIE_NAME_FID)

    if passport_uid and passport_uid.lower() != (native_uid or "").lower():
        return True
    if passport_fid and passport_fid.lower() != (native_fid or "").lower():
        return True
    return False
