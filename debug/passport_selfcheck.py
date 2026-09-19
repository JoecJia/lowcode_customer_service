"""超星 Passport 联调自检脚本。

用途：用真实调用把以下几个待定项一次钉死，失败项会打印原始返回便于排查：

1. 接口域名用 ``passport2-api.chaoxing.com`` 还是 ``passport2.chaoxing.com``
2. 签名私钥用 ``PASSPORT_APP_KEY``（生产）还是 ``PASSPORT_APP_KEY_DEBUG``
3. ``getVC3Secrets`` 返回的 md5Key AES 解密后是否等于本地常量
4. ``userinfo`` 是否接受 ``showproduct=false`` / ``ip`` 透传
5. 传入真实 Cookie 时，VC3 验签能否通过

用法（在项目根目录执行）::

    python debug/passport_selfcheck.py
    python debug/passport_selfcheck.py --cookie "UID=..; fid=..; vc3=..; _d=.."
"""

import argparse
import asyncio
import os
import sys
import time
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import httpx2  # noqa: E402
import config as cfg  # noqa: E402
from services import passport_service as ps  # noqa: E402
from services.passport_crypto import (  # noqa: E402
    aes_decode,
    gen_signature,
    md5_hex,
    package_param,
)

TIMEOUT = 20
CANDIDATE_BASES = [
    cfg.PASSPORT_BASE_URL,
    "https://passport2-api.chaoxing.com/",
    "https://passport2.chaoxing.com/",
]


def short(value: Any, keep: int = 8) -> str:
    text = "" if value is None else str(value)
    return "<empty>" if not text else f"{text[:keep]}...(len={len(text)})"


def title(text: str) -> None:
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


async def http_get(url: str, params: dict, signature: str, user_agent: str | None = None):
    headers = {"signature": signature}
    if user_agent:
        headers["User-Agent"] = user_agent
    async with httpx2.AsyncClient() as client:
        resp = await client.get(
            url, params=params, headers=headers, timeout=TIMEOUT, follow_redirects=True
        )
        try:
            return resp.status_code, resp.json()
        except Exception:  # noqa: BLE001
            return resp.status_code, resp.text[:300]


async def probe_vc3_secrets() -> tuple[str, str] | None:
    """探测「域名 + 签名私钥」组合，返回第一个成功的组合。"""
    title("Step 1 · 探测 getVC3Secrets：域名 × 签名私钥")

    combos: list[tuple[str, str, str]] = []
    for base in dict.fromkeys(CANDIDATE_BASES):
        combos.append((base, "prod", cfg.PASSPORT_APP_KEY_PROD))
        combos.append((base, "debug", cfg.PASSPORT_APP_KEY_DEBUG))

    winner: tuple[str, str] | None = None
    for base, mode, app_key in combos:
        if not app_key:
            continue
        params = {
            "appid": cfg.PASSPORT_APP_ID,
            "time": int(time.time() * 1000),
            "encryptType": "rsa_pub",
            "withSimulateKey": "true",
        }
        signature = gen_signature(app_key, params)
        label = f"{base} + {mode}"
        try:
            status, data = await http_get(f"{base}api/v2/getVC3Secrets", params, signature)
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {label} -> 请求异常: {exc}")
            continue

        if isinstance(data, dict) and data.get("result"):
            secrets = data.get("secrets") or []
            sim = data.get("simulateSecrets") or []
            print(f"[ OK ] {label} -> result=true, secrets={len(secrets)}, simulate={len(sim)}")
            if winner is None:
                winner = (base, mode)
                print("\n--- 密钥解密核对 ---")
                for group, items in (("secrets", secrets), ("simulateSecrets", sim)):
                    for idx, item in enumerate(items):
                        try:
                            pk = aes_decode(item.get("publicKey", ""), cfg.PASSPORT_VC3_AES_KEY)
                            mk = aes_decode(item.get("md5Key", ""), cfg.PASSPORT_VC3_AES_KEY)
                        except Exception as exc:  # noqa: BLE001
                            print(f"  {group}[{idx}] AES 解密失败: {exc}")
                            continue
                        expect = (
                            cfg.PASSPORT_SIMULATE_MD5_KEY
                            if group == "simulateSecrets"
                            else cfg.PASSPORT_MD5_KEY
                        )
                        flag = "OK" if mk == expect else f"不一致(期望 {expect})"
                        print(
                            f"  {group}[{idx}] md5Key={mk!r} [{flag}] "
                            f"publicKey->{short(pk, 16)}"
                        )
        else:
            msg = data.get("msg") if isinstance(data, dict) else data
            print(f"[FAIL] {label} -> {msg}")

    if winner:
        print(f"\n>>> 结论：使用域名 {winner[0]} ，签名私钥 {winner[1]}")
    else:
        print("\n>>> 未找到可用组合，请检查 appid/appkey 与网络/白名单")
    return winner


async def probe_userinfo(uid: str) -> None:
    title("Step 2 · 探测 userinfo：showproduct / ip 透传")

    now = int(time.time() * 1000)
    enc = md5_hex(package_param([uid, cfg.PASSPORT_API_USERINFO_KEY, now]))
    base_params: dict[str, Any] = {
        "appid": cfg.PASSPORT_APP_ID,
        "uid": uid,
        "enc": enc,
        "industry": "1",
        "last": "true",
        "time": now,
    }

    variants = [
        ("最小参数集(参考实现)", {}, None),
        ("+ showproduct=false", {"showproduct": "false"}, None),
        ("+ showproduct=false + ip", {"showproduct": "false", "ip": "127.0.0.1"}, None),
    ]

    for label, extra, ua in variants:
        params = {**base_params, **extra}
        signature = gen_signature(ps.PASSPORT_APP_KEY, params)
        try:
            status, data = await http_get(
                f"{ps.PASSPORT_BASE_URL}api/v2/userinfo", params, signature, ua
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {label} -> 请求异常: {exc}")
            continue
        if isinstance(data, dict) and data.get("result"):
            print(f"[ OK ] {label} -> realname={data.get('realname')!r} uid={data.get('uid')}")
        else:
            msg = data.get("mes") if isinstance(data, dict) else data
            print(f"[FAIL] {label} -> {msg}")


async def probe_service_chain(uid: str) -> None:
    title("Step 3 · 走我们自己的服务链路（缓存 → 验签依赖的密钥 → userinfo）")

    ps.clear_cache()
    secrets = await ps.get_vc3_secrets(True)
    print(f"get_vc3_secrets(simulate=True) -> {len(secrets)} 组密钥")
    for idx, item in enumerate(secrets):
        print(f"  [{idx}] md5Key={item['md5Key']!r} startTime={item.get('startTime')}")

    info = await ps.get_passport_user_info(uid)
    if info:
        print(f"get_passport_user_info -> realname={info.get('realname')!r}")
    else:
        print("get_passport_user_info -> 失败（见上方 [passport] 日志）")


async def probe_cookie_verify(cookie_text: str) -> None:
    title("Step 4 · 真实 Cookie 的 VC3 验签")

    jar: dict[str, str] = {}
    for part in cookie_text.split(";"):
        if "=" in part:
            key, _, value = part.partition("=")
            jar[key.strip()] = value.strip()

    uid = jar.get("UID", "")
    fid = jar.get("fid", "")
    vc3 = jar.get("vc3", "")
    login_time = jar.get("_d", "")
    print(f"UID={uid} fid={fid} vc3={short(vc3)} _d={login_time}")
    if not (uid and vc3 and login_time):
        print("Cookie 四要素不完整，跳过")
        return

    ok = await ps.is_login_passport(uid, vc3, login_time)
    print(f"is_login_passport -> {ok}")
    if not ok:
        print("提示：若 md5Key 与本地常量一致仍失败，请检查 vc3 的 '+' 解码差异")

    await ps.check_passport_vc3  # noqa: B018  保持引用，便于阅读


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookie", default="", help="真实浏览器 Cookie 串（可选）")
    parser.add_argument("--uid", default=os.environ.get("CHAOXING_MCP_UID", ""), help="用于探测的 uid")
    args = parser.parse_args()

    title("Step 0 · 当前配置")
    print(f"BASE_URL      = {cfg.PASSPORT_BASE_URL}")
    print(f"KEY_MODE      = {cfg.PASSPORT_KEY_MODE}")
    print(f"APP_ID        = {cfg.PASSPORT_APP_ID}")
    print(f"APP_KEY(prod) = {short(cfg.PASSPORT_APP_KEY_PROD)}")
    print(f"APP_KEY(debug)= {short(cfg.PASSPORT_APP_KEY_DEBUG)}")
    print(f"USERINFO_KEY  = {short(cfg.PASSPORT_API_USERINFO_KEY)}")
    print(f"AES_KEY       = {short(cfg.PASSPORT_VC3_AES_KEY)}")
    print(f"MD5_KEY       = {cfg.PASSPORT_MD5_KEY!r}")
    print(f"SIM_MD5_KEY   = {cfg.PASSPORT_SIMULATE_MD5_KEY!r}")
    print(f"FORWARD_INFO  = {cfg.PASSPORT_FORWARD_CLIENT_INFO}")

    winner = await probe_vc3_secrets()
    if winner:
        ps.PASSPORT_BASE_URL, mode = winner
        ps.PASSPORT_APP_KEY = (
            cfg.PASSPORT_APP_KEY_DEBUG if mode == "debug" else cfg.PASSPORT_APP_KEY_PROD
        )

    uid = args.uid or "168034620"
    await probe_userinfo(uid)
    await probe_service_chain(uid)

    if args.cookie:
        await probe_cookie_verify(args.cookie)
    else:
        title("Step 4 · 真实 Cookie 的 VC3 验签（已跳过）")
        print('如需验证，请带参数：--cookie "UID=..; fid=..; vc3=..; _d=.."')


if __name__ == "__main__":
    asyncio.run(main())
