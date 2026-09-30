r"""裸流测速脚本：绕过前端，直接测量后端 SSE 的真实生成速度。

用途
----
区分「前端渲染慢」与「模型生成慢」：
本脚本只做 HTTP 连接 + SSE 解析，不做任何 DOM 渲染、不等待渲染帧，
因此它测出的速率 = 后端（含多轮 Agent 调度与技能检索）+ 网络 的真实速率。

对比方法
--------
1) 跑本脚本，记下 content 速率 R_net；
2) 在浏览器里问同一个问题，用控制台日志算出可见速率 R_visible；
3) R_visible 明显低于 R_net（例如 30 字/秒 vs 90 字/秒）→ 瓶颈在前端渲染；
   两者接近 → 瓶颈在模型侧/多轮调度。

判定时重点看 content 速率，而不是总耗时。

用法
----
    venv\Scripts\python.exe debug\bench_chat_speed.py
    venv\Scripts\python.exe debug\bench_chat_speed.py -m "如何配置审批流程的节点条件"
    venv\Scripts\python.exe debug\bench_chat_speed.py -r 3
    venv\Scripts\python.exe debug\bench_chat_speed.py --base http://127.0.0.1:8000
    venv\Scripts\python.exe debug\bench_chat_speed.py --token <JWT>   # 跳过自动签发

（必须用项目虚拟环境 venv 里的解释器；系统 PATH 中的 python 是
 Microsoft Store 占位 stub，执行后无任何输出。）

结果同时写入 debug/bench_result.txt。

注意
----
脚本会真实调用大模型并写入数据库（新建会话 + 消息），请使用测试账号运行。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

from config import DB_PATH  # noqa: E402
from services.auth_service import create_token, register_user  # noqa: E402

DEFAULT_QUESTION = "如何配置审批流程的节点条件"
DEFAULT_BASE = "http://127.0.0.1:8000"
# 同一类型事件间隔超过该秒数即视为新的一段（用于切开多轮 Agent 循环之间的检索空档）
SEGMENT_GAP_SECONDS = 2.0
# 这些是后端插入的思考标记，不属于模型真实输出，统计字数时剔除
REASONING_MARKERS = ("<THINK_V2>", "</think>")


# ── 账号与鉴权 ──

def pick_user() -> dict:
    """从数据库取一个可用账号；库中无账号时自动注册一个测速专用账号。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, username, role, can_chat, can_admin FROM users ORDER BY id LIMIT 1"
        ).fetchone()
    if row:
        return dict(row)

    created = register_user("bench_bot", "bench_bot_pwd_2026", can_chat=1, can_admin=0)
    if not created.get("ok"):
        raise SystemExit(f"数据库无可用账号，自动注册也失败：{created.get('detail')}")
    print("[setup] 数据库为空，已自动注册测试账号 bench_bot")
    return {
        "id": created["user_id"],
        "username": created["username"],
        "role": "user",
        "can_chat": 1,
        "can_admin": 0,
    }


def make_token() -> str:
    user = pick_user()
    return create_token(
        user["id"],
        user["username"],
        user["role"],
        int(user.get("can_chat") or 1),
        int(user.get("can_admin") or 0),
    )


# ── HTTP 辅助 ──

def http_post(url: str, body: dict, token: str, timeout: int = 600):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    return urllib.request.urlopen(req, timeout=timeout)


def new_session(base: str, token: str) -> str:
    try:
        with http_post(
            f"{base}/api/chat",
            {"session_id": "", "message": "", "new_session": True},
            token,
            timeout=30,
        ) as resp:
            sid = resp.headers.get("X-Session-Id") or ""
            resp.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"创建会话失败：HTTP {e.code} {e.read().decode('utf-8', 'replace')[:200]}")
    except urllib.error.URLError as e:
        raise SystemExit(f"无法连接后端 {base}：{e.reason}")
    if not sid:
        raise SystemExit("创建会话失败：响应缺少 X-Session-Id")
    return sid


def event_text(data: str) -> str:
    """从 SSE data 行提取 content 文本。"""
    if not data or data == "{}":
        return ""
    try:
        obj = json.loads(data)
    except json.JSONDecodeError:
        return ""
    if not isinstance(obj, dict):
        return ""
    return str(obj.get("content") or "")


# ── 单次测速 ──

def run_once(
    base: str,
    token: str,
    question: str,
    index: int,
    total: int,
    dump_reasoning: bool = False,
) -> dict:
    print(f"\n{'─' * 58}")
    print(f"第 {index}/{total} 次 · 问题：{question}")
    sid = new_session(base, token)
    print(f"会话：{sid}")

    t0 = time.perf_counter()
    ttfb: float | None = None
    first_content: float | None = None
    done_at: float | None = None
    segments: dict[str, list[dict]] = {"reasoning": [], "content": []}
    counts = {"reasoning": 0, "content": 0}
    chars = {"reasoning": 0, "content": 0}
    tasks: list[tuple[float, str]] = []
    # 诊断用：完整文本（用于统计 <task> 块出现在哪个通道）+ warning 事件
    full_text: dict[str, list[str]] = {"reasoning": [], "content": []}
    warnings: list[tuple[float, str]] = []

    try:
        with http_post(
            f"{base}/api/chat",
            {"session_id": sid, "message": question, "new_session": False},
            token,
        ) as resp:
            event_type = ""
            data_line = ""
            while True:
                raw = resp.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")

                if line.startswith("event:"):
                    event_type = line[6:].strip()
                    continue
                if line.startswith("data:"):
                    data_line = line[5:].strip()
                    continue
                if line != "":
                    continue

                # 空行 = 一个 SSE 事件结束
                now = time.perf_counter() - t0
                if ttfb is None:
                    ttfb = now

                if event_type == "error":
                    raise SystemExit(f"后端返回错误：{data_line}")

                if event_type in ("reasoning", "content"):
                    text = event_text(data_line)
                    for marker in REASONING_MARKERS:
                        text = text.replace(marker, "")
                    if text:
                        full_text[event_type].append(text)
                        counts[event_type] += 1
                        chars[event_type] += len(text)
                        segs = segments[event_type]
                        if not segs or now - segs[-1]["last"] > SEGMENT_GAP_SECONDS:
                            segs.append({"start": now, "last": now, "chars": 0, "events": 0})
                        seg = segs[-1]
                        seg["last"] = now
                        seg["chars"] += len(text)
                        seg["events"] += 1
                        if event_type == "content" and first_content is None:
                            first_content = now

                elif event_type == "task":
                    try:
                        tasks.append((now, str(json.loads(data_line).get("type") or "?")))
                    except json.JSONDecodeError:
                        tasks.append((now, "?"))

                elif event_type == "warning":
                    try:
                        warnings.append((now, str(json.loads(data_line).get("content") or "")))
                    except json.JSONDecodeError:
                        warnings.append((now, data_line))

                elif event_type == "done":
                    done_at = now

                event_type, data_line = "", ""

    except urllib.error.HTTPError as e:
        raise SystemExit(f"对话请求失败：HTTP {e.code} {e.read().decode('utf-8', 'replace')[:200]}")
    except urllib.error.URLError as e:
        raise SystemExit(f"无法连接后端 {base}：{e.reason}")

    spent = (done_at if done_at is not None else time.perf_counter() - t0)

    # ── 报告 ──
    print(f"首事件延迟(TTFB)   : {ttfb:.2f} s" if ttfb is not None else "首事件延迟(TTFB)   : -")
    print(
        f"首字延迟(首个 content): "
        f"{first_content:.2f} s" if first_content is not None else "首字延迟(首个 content): -"
    )
    print(f"总耗时            : {spent:.2f} s")
    print(
        f"reasoning         : {chars['reasoning']} 字 / {counts['reasoning']} 事件"
    )
    print(f"content           : {chars['content']} 字 / {counts['content']} 事件")
    if tasks:
        print(f"task 调用         : {len(tasks)} 次 → {', '.join(t for _, t in tasks)}")
    else:
        print("task 调用         : 0 次")

    # ── 任务规划诊断 ──
    task_block_re = re.compile(r"<task>[\s\S]*?</task>", re.IGNORECASE)
    reasoning_task_blocks = task_block_re.findall("".join(full_text["reasoning"]))
    content_task_blocks = task_block_re.findall("".join(full_text["content"]))

    print("\n[任务规划诊断]")
    print(f"  reasoning 中 <task> 块 : {len(reasoning_task_blocks)} 个")
    print(f"  content   中 <task> 块 : {len(content_task_blocks)} 个")
    print(f"  后端实际执行 task      : {len(tasks)} 次")
    if reasoning_task_blocks and not content_task_blocks:
        print("  → task 全部取自 reasoning（自由思考文本），content 通道为 0")
    if content_task_blocks:
        print("  → [!] content 中残留 <task>，后端过滤失效，会直接泄漏给用户")
    for wt, wmsg in warnings:
        print(f"  ⚠ {wt:6.2f}s  warning: {wmsg}")
    if not warnings:
        print("  warning 事件          : 无")

    # 兜底路径排查：模型转向 feedback_form_link / clarifying_questions 时，
    # 打印思考过程尾部——决策依据通常出现在思考的最后一段
    fallback_markers = ("feedback_form_link", "clarifying_questions")
    hit_fallback = sorted({t for _, t in tasks if any(m in t for m in fallback_markers)})
    if hit_fallback or dump_reasoning:
        if hit_fallback:
            print("\n[!] 检测到兜底路径调用：" + ", ".join(hit_fallback))
        tail = "".join(full_text["reasoning"])[-2000:]
        print("\n----- 思考过程尾部（最后 2000 字） -----")
        print(tail)
        print("----- 思考过程尾部结束 -----")

    print("\n时间轴：")
    entries: list[tuple[float, str]] = []
    for kind in ("reasoning", "content"):
        for seg in segments[kind]:
            entries.append(
                (seg["start"], f"{kind:<9} {seg['chars']:>5d} 字 / {seg['events']:>4d} 事件")
            )
    for tk_time, tk_type in tasks:
        entries.append((tk_time, f"      └─ dispatch {tk_type}"))
    entries.sort(key=lambda x: x[0])
    for entry_time, label in entries:
        print(f"  {entry_time:7.2f}s  {label}")

    if counts["content"] == 0:
        print(
            "\n[!] 本次未收到任何 content 事件：模型可能在多轮循环中耗尽轮次，\n"
            "    前端会表现为「只有思考过程、没有最终回答」。"
        )

    rates: dict[str, list[float]] = {"reasoning": [], "content": []}
    for kind in ("reasoning", "content"):
        segs = segments[kind]
        if not segs:
            continue
        print(f"\n{kind} 分段速率：")
        for i, seg in enumerate(segs, 1):
            span = max(seg["last"] - seg["start"], 1e-6)
            rate = seg["chars"] / span
            rates[kind].append(rate)
            print(
                f"  #{i}  {seg['start']:6.2f}s → {seg['last']:6.2f}s   "
                f"{seg['chars']:5d} 字 / {seg['events']:4d} 事件 / {span:6.2f}s  →  {rate:6.1f} 字/秒"
            )

    return {
        "sid": sid,
        "ttfb": ttfb,
        "first_content": first_content,
        "spent": spent,
        "content_chars": chars["content"],
        "content_events": counts["content"],
        "reasoning_chars": chars["reasoning"],
        "content_rates": rates["content"],
        "reasoning_rates": rates["reasoning"],
        "reasoning_task_blocks": len(reasoning_task_blocks),
        "content_task_blocks": len(content_task_blocks),
        "task_types": [tk for _, tk in tasks],
        "warnings": [w for _, w in warnings],
    }


def install_tee(path: str) -> None:
    """把输出同时写入文件，避免终端/管道吞掉长任务的输出。"""
    try:
        fh = open(path, "w", encoding="utf-8")
    except OSError:
        return

    real = sys.__stdout__

    class _Tee:
        def write(self, s: str) -> int:
            fh.write(s)
            fh.flush()
            try:
                if real is not None:
                    real.write(s)
                    real.flush()
            except Exception:
                pass
            return len(s)

        def flush(self) -> None:
            fh.flush()

    sys.stdout = _Tee()  # type: ignore[assignment]


def main() -> int:
    parser = argparse.ArgumentParser(description="后端 SSE 裸流测速（绕过前端渲染）")
    parser.add_argument("-m", "--message", default=DEFAULT_QUESTION, help="测速用的问题（固定同一个才有可比性）")
    parser.add_argument("-r", "--repeat", type=int, default=1, help="重复次数，取平均")
    parser.add_argument("--base", default=DEFAULT_BASE, help="后端地址，默认 http://127.0.0.1:8000")
    parser.add_argument("--token", default="", help="直接指定 JWT，跳过自动签发")
    parser.add_argument(
        "--dump-reasoning",
        action="store_true",
        help="输出思考过程尾部；检测到兜底路径（feedback_form_link / clarifying_questions）时会自动输出",
    )
    parser.add_argument(
        "--out",
        default=os.path.join(ROOT_DIR, "debug", "bench_result.txt"),
        help="日志落盘路径（默认 debug/bench_result.txt）",
    )
    args = parser.parse_args()

    install_tee(args.out)

    token = args.token or make_token()

    # 连通性预检
    try:
        with urllib.request.urlopen(f"{args.base}/health", timeout=5) as r:
            r.read()
    except Exception as e:
        raise SystemExit(f"后端 {args.base} 不可用：{e}")

    print("=" * 58)
    print("后端 SSE 裸流测速（不含任何前端渲染开销）")
    print(f"后端地址：{args.base}")
    print("=" * 58)

    results = []
    for i in range(1, max(1, args.repeat) + 1):
        results.append(run_once(args.base, token, args.message, i, max(1, args.repeat), args.dump_reasoning))

    # ── 汇总 ──
    all_content_rates = [r for res in results for r in res["content_rates"]]
    print(f"\n{'═' * 58}")
    print("汇总")
    print(f"{'═' * 58}")
    print(f"运行次数            : {len(results)}")
    for i, res in enumerate(results, 1):
        rate = res["content_rates"][0] if res["content_rates"] else 0.0
        ttfb_txt = f"{res['ttfb']:.2f}s" if res["ttfb"] is not None else "-"
        first_txt = f"{res['first_content']:.2f}s" if res["first_content"] is not None else "-"
        print(
            f"  第 {i} 次: TTFB {ttfb_txt} | 首字 {first_txt} | 总 {res['spent']:.2f}s | "
            f"content {res['content_chars']} 字 | {rate:.1f} 字/秒"
        )
    print("\n任务规划稳定性：")
    task_counts: list[int] = []
    for i, res in enumerate(results, 1):
        types = res["task_types"]
        task_counts.append(len(types))
        counter: dict[str, int] = {}
        for tk in types:
            counter[tk] = counter.get(tk, 0) + 1
        detail = ", ".join(f"{k}×{v}" for k, v in counter.items()) or "无"
        print(
            f"  第 {i} 次: task {len(types)} 次 | reasoning 内 <task> 块 "
            f"{res['reasoning_task_blocks']} 个 | {detail}"
        )
    if len(results) > 1:
        print(f"  task 数波动         : {min(task_counts)} ~ {max(task_counts)}（同一问题，反映规划随机性）")
    warned = sum(1 for r in results if r["warnings"])
    print(f"  触发 warning 的次数 : {warned}/{len(results)}")
    # 跑偏率：出现兜底/反问路径的次数（正常回答不应调用这两个技能）
    fallback_marks = ("feedback_form_link", "clarifying_questions")
    drift = sum(
        1
        for r in results
        if any(any(m in t for m in fallback_marks) for t in r["task_types"])
    )
    print(f"  走兜底/反问路径     : {drift}/{len(results)}")

    firsts = [r["first_content"] for r in results if r["first_content"] is not None]
    if firsts:
        print(
            f"  首字延迟分布        : 最小 {min(firsts):.1f}s / "
            f"平均 {sum(firsts) / len(firsts):.1f}s / 最大 {max(firsts):.1f}s"
        )
    no_answer = sum(1 for r in results if r["content_chars"] == 0)
    print(f"  无最终回答的次数    : {no_answer}/{len(results)}")

    if all_content_rates:
        avg = sum(all_content_rates) / len(all_content_rates)
        print(f"\ncontent 平均速率    : {avg:.1f} 字/秒   ← R_net，拿去和浏览器可见速率对比")
    else:
        print("\n[!] 未捕获到任何 content 事件，请检查后端日志。")

    print(
        "\n判定：浏览器里正常发问时，若可见速率明显低于上面的 R_net（例如 30 vs 90），\n"
        "      则瓶颈在前端渲染（api/chat.ts 的逐 token 强制渲染帧）；\n"
        "      若两者接近，则瓶颈在模型侧或多轮 Agent 调度。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
