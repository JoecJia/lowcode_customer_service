"""VC3 验签逐步诊断脚本。

把浏览器里的 Cookie 值贴进来，脚本会真实调用 passport 拉取公钥，逐步输出
"URL 解码 → MD5 尾校验 → RSA 验签" 每一环的结果，用于定位验签失败的确切原因。

用法（在项目根目录执行）::

    python debug/verify_vc3.py --cookie "UID=168034620; fid=354241; vc3=xxxxx; _d=1700000000000"

    # vc3 值较长时，建议从文件读取，避免命令行转义问题
    python debug/verify_vc3.py --vc3-file vc3.txt --uid 168034620 --time 1700000000000
"""

import argparse
import asyncio
import os
import re
import sys
from urllib.parse import unquote, unquote_plus

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import config as cfg  # noqa: E402
from services import passport_service as ps  # noqa: E402
from services.passport_crypto import ENC_LEN, md5_hex, rsa_check  # noqa: E402


def short(text: str, keep: int = 12) -> str:
    if not text:
        return "<empty>"
    return f"{text[:keep]}...({len(text)} chars)"


def parse_cookie(text: str) -> dict:
    jar: dict[str, str] = {}
    for part in (text or "").split(";"):
        if "=" in part:
            key, _, value = part.partition("=")
            jar[key.strip()] = value.strip()
    return jar


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookie", default="", help="完整 Cookie 串")
    parser.add_argument("--uid", default="")
    parser.add_argument("--time", default="", help="即 _d 的值")
    parser.add_argument("--vc3", default="")
    parser.add_argument("--vc3-file", default="", help="从文件读取 vc3（避免命令行转义）")
    args = parser.parse_args()

    jar = parse_cookie(args.cookie)
    uid = args.uid or jar.get("UID", "")
    login_time = args.time or jar.get("_d", "")
    vc3 = args.vc3 or jar.get("vc3", "")
    fid = jar.get("fid", "")
    if args.vc3_file:
        with open(args.vc3_file, encoding="utf-8") as f:
            vc3 = f.read().strip()

    section("Step 0 · 输入")
    print(f"BASE_URL      = {cfg.PASSPORT_BASE_URL}")
    print(f"KEY_MODE      = {cfg.PASSPORT_KEY_MODE} (appkey 前 8 位: {cfg.PASSPORT_APP_KEY[:8]})")
    print(f"UID           = {uid!r}")
    print(f"fid           = {fid!r}")
    print(f"_d            = {login_time!r}")
    print(f"vc3           = {short(vc3)}")

    if not uid or not vc3 or not login_time:
        print("\n!! UID / vc3 / _d 三者缺一，无法继续。请检查粘贴内容。")
        return

    section("Step 1 · 基础校验")
    uid_is_numeric = bool(re.fullmatch(r"[+-]?[0-9]+", uid.strip()))
    time_is_numeric = bool(re.fullmatch(r"[0-9]+", login_time.strip()))
    print(f"uid 是纯数字            : {uid_is_numeric}")
    print(f"_d 是纯数字             : {time_is_numeric}  (长度 {len(login_time.strip())})")
    print(f"vc3 长度 > {ENC_LEN}          : {len(vc3) > ENC_LEN}  (实际 {len(vc3)})")
    if not (uid_is_numeric and time_is_numeric and len(vc3) > ENC_LEN):
        print("\n!! 基础校验未通过：_d 必须是纯数字时间戳，vc3 长度必须大于 32。")
        print("   （若 _d 不是纯数字，说明搬错了 Cookie）")
        return

    section("Step 2 · URL 解码")
    cand_plus = unquote_plus(vc3)
    cand_plain = unquote(vc3)
    print(f"unquote_plus(Java 语义) : {short(cand_plus)}")
    print(f"unquote(保留 + )        : {short(cand_plain)}")
    print(f"二者是否相同            : {cand_plus == cand_plain}")
    candidates = [("unquote_plus", cand_plus)]
    if cand_plus != cand_plain:
        candidates.append(("unquote", cand_plain))

    content = f"[{uid.strip()}][{login_time.strip()}]"
    print(f"\n验签内容 content        : {content!r}")

    any_pass = False
    for simulate in (False, True):
        section(f"Step 3 · 密钥组 {'模拟登录 simulateSecrets' if simulate else '正式登录 secrets'}")
        secrets = await ps.get_vc3_secrets(simulate)
        print(f"拉取到 {len(secrets)} 组密钥")
        if not secrets:
            print("!! 该组密钥为空（getVC3Secrets 失败或无权限）")
            continue
        for idx, item in enumerate(secrets):
            print(
                f"  密钥[{idx}] startTime={item.get('startTime')} "
                f"md5Key={item['md5Key']!r} publicKey={short(item['publicKey'], 24)}"
            )

        for label, decoded in candidates:
            print(f"\n  --- 解码方式: {label} ---")
            if len(decoded) <= ENC_LEN:
                print("    解码后长度不足，跳过")
                continue
            end_enc = decoded[-ENC_LEN:]
            sign_part = decoded[: -ENC_LEN]
            print(f"    endEnc(后32位) = {end_enc}")
            print(f"    sigPart 长度   = {len(sign_part)}")

            for idx, item in enumerate(secrets):
                calc = md5_hex(sign_part + item["md5Key"])
                match = calc == end_enc
                print(f"    密钥[{idx}] MD5 尾校验: {'[OK] 通过' if match else '[NG] 不匹配'}"
                      f"{'' if match else f' (计算值 {calc[:12]}...)'}")
                if not match:
                    continue
                ok = rsa_check(content, sign_part, item["publicKey"])
                print(f"    密钥[{idx}] RSA 验签  : {'[OK] 通过' if ok else '[NG] 失败'}")
                if ok:
                    any_pass = True

    section("结论")
    if any_pass:
        print("[OK] 验签通过 —— 这组 Cookie 本身是有效的。")
        print("   如果生产接口仍返回 401，请检查后端是否真的收到了这 4 个 Cookie")
        print("   （看后端日志 [passport-cookie] 那行的长度），以及 host 是否为 service.cxlowcode.com。")
    else:
        print("[NG] 验签未通过。常见原因（按概率排序）：")
        print("   1) vc3 与 _d 不是同一次登录产生 / vc3 已过期（Cookie 失效期 7 天或 30 天）")
        print("   2) vc3 不是由我们申请的这个 passport 应用（appid）签发，" 
              "md5Key/公钥自然对不上 → 需向平台确认 cxlowcode 平台用的是哪个 appid")
        print("   3) 复制值的过程中被截断或转义")


if __name__ == "__main__":
    asyncio.run(main())
