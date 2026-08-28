"""Chaoxing MCP token 服务：按签名规则获取 token，内存缓存，过期自动刷新。

token 接口规则（已验证）：
  - GET {CHAOXING_MCP_TOKEN_URL}，query 参数：
      datetime: 当前时间，格式 yyyyMMddHH（小时粒度）
      type/fid/uid/sign: 业务标识
      enc: md5("[datetime={dt}][fid={fid}][sign={sign}][type={type}][uid={uid}][{key}]")
  - 需携带浏览器请求头（UA/Accept/Referer/Origin），否则 403
  - 响应：{"data":{"token":"<jwt>"},"success":true}
  - token 有效期 24h，过期时间从 JWT payload 的 exp 字段解析

缓存策略：内存缓存 + 提前 5 分钟视为过期，调用前可先检查 token_is_fresh()。
"""

import base64
import hashlib
import json
import time
from datetime import datetime

import httpx2

from config import (
    CHAOXING_MCP_FID,
    CHAOXING_MCP_KEY,
    CHAOXING_MCP_SIGN,
    CHAOXING_MCP_TOKEN_URL,
    CHAOXING_MCP_TYPE,
    CHAOXING_MCP_UID,
    DEBUG,
)

# 提前刷新阈值（秒）：距离过期不足该时长视为失效
_REFRESH_MARGIN_SECONDS = 300

# token 缓存：kind -> (token, expires_at)
_cache: dict[str, tuple[str, float]] = {}

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "http://m.oa.chaoxing.com/",
    "Origin": "http://m.oa.chaoxing.com",
}


def _build_enc(dt: str) -> str:
    source = (
        f"[datetime={dt}][fid={CHAOXING_MCP_FID}][sign={CHAOXING_MCP_SIGN}]"
        f"[type={CHAOXING_MCP_TYPE}][uid={CHAOXING_MCP_UID}][{CHAOXING_MCP_KEY}]"
    )
    return hashlib.md5(source.encode("utf-8")).hexdigest()


def _decode_jwt_exp(token: str) -> float:
    """从 JWT payload 解析 exp（秒）。"""
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload))
    return float(data["exp"])


async def _fetch_chaoxing_token() -> tuple[str, float]:
    """获取 token，返回 (token, expires_at 时间戳)。"""
    dt = datetime.now().strftime("%Y%m%d%H")
    params = {
        "datetime": dt,
        "type": CHAOXING_MCP_TYPE,
        "fid": CHAOXING_MCP_FID,
        "uid": CHAOXING_MCP_UID,
        "sign": CHAOXING_MCP_SIGN,
        "enc": _build_enc(dt),
    }
    async with httpx2.AsyncClient(headers=_BROWSER_HEADERS) as client:
        resp = await client.get(CHAOXING_MCP_TOKEN_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("success"):
        raise RuntimeError(f"Chaoxing token 获取失败: {data.get('msg') or data}")

    token = data["data"]["token"]
    expires_at = _decode_jwt_exp(token)
    return token, expires_at


async def get_bearer_token() -> str:
    """返回有效 token；缓存过期则自动重新获取。"""
    now = time.time()
    cached = _cache.get("chaoxing-mcp")
    if cached and cached[1] > now + _REFRESH_MARGIN_SECONDS:
        return cached[0]

    token, expires_at = await _fetch_chaoxing_token()
    _cache["chaoxing-mcp"] = (token, expires_at)
    if DEBUG:
        import sys

        print(
            f"[chaoxing-token] 已刷新 token，有效期至 {datetime.fromtimestamp(expires_at)}",
            file=sys.stderr,
        )
    return token


def token_is_fresh() -> bool:
    """token 是否仍在有效期内（含提前量）。"""
    cached = _cache.get("chaoxing-mcp")
    return bool(cached and cached[1] > time.time() + _REFRESH_MARGIN_SECONDS)
