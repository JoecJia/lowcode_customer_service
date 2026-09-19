"""超星 Passport 服务。

职责（严格对齐 Java 参考实现 ``passport-cookie-login``）：

1. ``get_vc3_secrets``：拉取 VC3 公钥与 md5Key（AES 解密后缓存，默认 24 小时）
2. ``is_login_passport`` / ``check_passport_vc3``：校验 Cookie 中的 vc3 签名（先正式、后模拟）
3. ``get_passport_user_info``：按 uid 查询用户信息（取真实姓名）

对外接口均为 async；外部调用统一走 ``httpx2.AsyncClient``（与 ``mcp_token_service`` 一致）。
"""

from __future__ import annotations

import re
import sys
import time
from typing import Any

import httpx2

from config import (
    DEBUG,
    PASSPORT_API_USERINFO_KEY,
    PASSPORT_APP_ID,
    PASSPORT_APP_KEY,
    PASSPORT_BASE_URL,
    PASSPORT_FORWARD_CLIENT_INFO,
    PASSPORT_MD5_KEY,
    PASSPORT_SIMULATE_MD5_KEY,
    PASSPORT_VC3_AES_KEY,
)
from services.passport_crypto import (
    ENC_LEN,
    aes_decode,
    decode_url,
    gen_signature,
    md5_hex,
    package_param,
    rsa_check,
)

# ── 缓存 key（对齐 Java 参考实现）──
CACHE_KEY_VC3_SECRETS = "passport:vc3:secrets"
CACHE_KEY_VC3_SIMULATE_SECRETS = "passport:vc3:simulate:secrets"

# 官方文档建议「每天凌晨拉取一次」→ 本地缓存 24 小时
SECRET_CACHE_TTL_SECONDS = 24 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 20

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_NUMERIC = re.compile(r"[0-9]+")
_INT_LIKE = re.compile(r"[+-]?[0-9]+")

# 内存缓存：key -> (value, expires_at)
_cache: dict[str, tuple[Any, float]] = {}


def _debug(*args: Any) -> None:
    if DEBUG:
        print("[passport]", *args, file=sys.stderr)


def short(value: Any) -> str:
    """日志用的脱敏摘要：只保留长度与前 8 位，避免打印密钥/签名全文。"""
    text = "" if value is None else str(value)
    if not text:
        return "<empty>"
    return f"{text[:8]}...(len={len(text)})"


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
    """清空内存缓存（自检脚本用）。"""
    _cache.clear()


def _safe_aes_decode(cipher_text: str | None) -> str:
    try:
        return aes_decode(cipher_text or "", PASSPORT_VC3_AES_KEY)
    except Exception as exc:  # noqa: BLE001
        _debug("AES 解密失败:", exc)
        return ""


# ────────────────────────── VC3 密钥 ──────────────────────────


def make_signature_headers(params: dict[str, Any]) -> dict[str, str]:
    """按参数生成 passport 通用请求头。"""
    return {"signature": gen_signature(PASSPORT_APP_KEY, params)}


async def get_vc3_secrets(simulate: bool) -> list[dict[str, Any]]:
    """获取 VC3 密钥列表（含解密后的 publicKey / md5Key），缓存优先。

    :param simulate: True 取模拟登录密钥组（simulateSecrets），False 取正式密钥组（secrets）
    """
    cache_key = CACHE_KEY_VC3_SIMULATE_SECRETS if simulate else CACHE_KEY_VC3_SECRETS
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    fallback_md5_key = PASSPORT_SIMULATE_MD5_KEY if simulate else PASSPORT_MD5_KEY
    params: dict[str, Any] = {
        "appid": PASSPORT_APP_ID,
        "time": int(time.time() * 1000),
        "encryptType": "rsa_pub",
        "withSimulateKey": "true" if simulate else "false",
    }

    try:
        async with httpx2.AsyncClient() as client:
            resp = await client.get(
                f"{PASSPORT_BASE_URL}api/v2/getVC3Secrets",
                params=params,
                headers=make_signature_headers(params),
                timeout=REQUEST_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        _debug("getVC3Secrets 调用异常:", exc)
        return []

    if not data.get("result"):
        _debug("getVC3Secrets 返回失败:", data.get("msg"))
        return []

    raw_secrets = data.get("simulateSecrets") if simulate else data.get("secrets")
    if not raw_secrets:
        _debug("getVC3Secrets 密钥列表为空, simulate=", simulate)
        return []

    secrets: list[dict[str, Any]] = []
    for item in raw_secrets:
        public_key = _safe_aes_decode(item.get("publicKey"))
        if not public_key:
            # 解密失败的公钥直接剔除（对齐 Java 参考实现）
            continue
        # md5Key 同样是 AES 加密的；解密失败时回退到配置常量
        md5_key = _safe_aes_decode(item.get("md5Key")) or fallback_md5_key
        if md5_key != fallback_md5_key:
            _debug("提示: 接口返回的 md5Key 与本地常量不一致，已采用接口返回值")
        secrets.append(
            {
                "publicKey": public_key,
                "md5Key": md5_key,
                "startTime": item.get("startTime"),
            }
        )

    if secrets:
        _cache_set(cache_key, secrets, SECRET_CACHE_TTL_SECONDS)
        _debug(f"VC3 密钥已缓存, simulate={simulate}, count={len(secrets)}")
    else:
        _debug("VC3 密钥解密后全部为空, simulate=", simulate)

    return secrets


# ────────────────────────── VC3 验签 ──────────────────────────


def _decode_candidates(sign: str) -> list[str]:
    """vc3 的 URL 解码候选。

    Java 用 ``URLDecoder.decode``（``+`` → 空格），Python ``unquote`` 不会。
    这里以 Java 语义为主，另一个作为兜底，两者结果相同时只保留一个。
    """
    primary = decode_url(sign, plus_as_space=True)
    secondary = decode_url(sign, plus_as_space=False)
    return [primary] if primary == secondary else [primary, secondary]


async def check_passport_vc3(sign: str, uid: str, login_time: str, simulate: bool) -> bool:
    """校验单个密钥组下的 vc3 签名。"""
    if len(sign) <= ENC_LEN or not _NUMERIC.fullmatch(login_time or ""):
        return False

    secrets = await get_vc3_secrets(simulate)
    if not secrets:
        _debug("VC3 密钥为空, uid=", uid, "simulate=", simulate)
        return False

    content = f"[{uid}][{login_time}]"

    for decoded in _decode_candidates(sign):
        if len(decoded) <= ENC_LEN:
            continue
        end_enc = decoded[-ENC_LEN:]
        sign_part = decoded[: -ENC_LEN]
        for secret in secrets:
            if md5_hex(sign_part + secret["md5Key"]) != end_enc:
                continue
            if rsa_check(content, sign_part, secret["publicKey"]):
                return True

    _debug("vc3 验签未通过, uid=", uid, "simulate=", simulate)
    return False


async def is_login_passport(uid: str | None, sign: str | None, timestamp: str | None) -> bool:
    """判断 Passport Cookie 是否有效：先正式登录验签，失败再试模拟登录。"""
    if not uid or not sign or not timestamp:
        return False
    if not str(uid).strip() or not str(sign).strip() or not str(timestamp).strip():
        return False
    if not _INT_LIKE.fullmatch(str(uid).strip()):
        _debug("uid 不是有效数字:", uid)
        return False

    uid = str(uid).strip()
    sign = str(sign).strip()
    timestamp = str(timestamp).strip()

    if await check_passport_vc3(sign, uid, timestamp, simulate=False):
        return True
    return await check_passport_vc3(sign, uid, timestamp, simulate=True)


# ────────────────────────── 用户信息 ──────────────────────────


async def get_passport_user_info(
    uid: str,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any] | None:
    """按 uid 查询 passport 用户信息，失败只记日志不抛异常（与参考实现一致）。"""
    try:
        now = int(time.time() * 1000)
        enc = md5_hex(package_param([uid, PASSPORT_API_USERINFO_KEY, now]))

        params: dict[str, Any] = {
            "appid": PASSPORT_APP_ID,
            "uid": str(uid),
            "enc": enc,
            "industry": "1",
            "last": "true",
            "showproduct": "false",
            "time": now,
        }
        if PASSPORT_FORWARD_CLIENT_INFO and client_ip:
            params["ip"] = client_ip

        headers = make_signature_headers(params)
        headers["User-Agent"] = (
            user_agent if (PASSPORT_FORWARD_CLIENT_INFO and user_agent) else _DEFAULT_USER_AGENT
        )

        async with httpx2.AsyncClient() as client:
            resp = await client.get(
                f"{PASSPORT_BASE_URL}api/v2/userinfo",
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        _debug("userinfo 调用异常, uid=", uid, exc)
        return None

    if not data.get("result"):
        _debug("userinfo 返回失败, uid=", uid, "msg=", data.get("mes"))
        return None
    return data
