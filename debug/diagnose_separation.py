"""
诊断脚本：直接调用 API 捕获完整 SSE 流，分析思考过程与最终回答的分离情况。
"""
import json
import os
import sys
import urllib.request
import urllib.error

from dotenv import load_dotenv

load_dotenv()

BASE = "http://127.0.0.1:8001"


def register_and_login(username: str, password: str) -> str:
    """注册并登录，返回 token；如已存在则直接登录"""
    # 先尝试注册
    try:
        req = urllib.request.Request(
            f"{BASE}/api/register",
            data=json.dumps({"username": username, "password": password}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        if data.get("ok"):
            print(f"  [注册] {username} 成功")
        else:
            print(f"  [注册] {data}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 409 or "already exists" in body.lower() or "exists" in body.lower():
            print(f"  [注册] 用户已存在，直接登录")
        elif e.code == 422:
            print(f"  [注册失败] 422: {body}")
            raise
        else:
            print(f"  [注册失败] {e.code}: {body}")
            raise

    # 登录
    req = urllib.request.Request(
        f"{BASE}/api/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [登录失败] {e.code}: {body}")
        raise
    data = json.loads(resp.read())
    token = data.get("access_token") or data.get("token")
    return token


def stream_chat(token: str, session_id: str, message: str):
    """发起流式聊天，返回原始 SSE 字节"""
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=json.dumps({
            "session_id": session_id,
            "message": message,
            "new_session": False,
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=180)
    return resp


def parse_sse_lines(body: bytes) -> list[dict]:
    """解析原始 SSE 字节，返回事件列表"""
    events = []
    lines = body.decode("utf-8", errors="replace").split("\n")
    event_type = ""
    data_str = ""

    for line in lines:
        line = line.strip()
        if not line:
            if event_type or data_str:
                try:
                    parsed = json.loads(data_str) if data_str and data_str != "{}" else {}
                except json.JSONDecodeError:
                    parsed = {"_raw": data_str}
                events.append({"event": event_type, "data": parsed})
                event_type = ""
                data_str = ""
            continue
        if line.startswith("event: "):
            event_type = line[7:].strip()
        elif line.startswith("data: "):
            data_str = line[6:].strip()

    if event_type or data_str:
        try:
            parsed = json.loads(data_str) if data_str and data_str != "{}" else {}
        except json.JSONDecodeError:
            parsed = {"_raw": data_str}
        events.append({"event": event_type, "data": parsed})

    return events


def create_session(token: str) -> str:
    """创建新会话"""
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=json.dumps({
            "session_id": "",
            "message": "",
            "new_session": True,
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=10)
    sid = resp.headers.get("X-Session-Id", "")
    # read the body to complete
    resp.read()
    return sid


def main():
    print("=" * 70)
    print("端到端诊断：SSE 流分析")
    print("=" * 70)

    # 1. 登录
    print("\n[1] 登录...")
    token = register_and_login("diagnose_test", "test1234")
    print(f"   Token: {token[:20]}...")

    # 2. 创建新会话
    print("\n[2] 创建新会话...")
    sid = create_session(token)
    print(f"   Session ID: {sid}")

    # 使用 "数据推送是什么" 作为测试问题（较短）
    question = "数据推送是什么"
    print(f"\n[3] 发送问题: {question}")

    try:
        resp = stream_chat(token, sid, question)
        raw_body = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"   错误: HTTP {e.code}\n{body}")
        return
    except Exception as e:
        print(f"   异常: {e}")
        return

    events = parse_sse_lines(raw_body)

    print(f"\n[4] 收到 {len(events)} 个 SSE 事件:\n")
    print("-" * 70)

    # 按类型分组统计
    from collections import Counter
    type_counts = Counter(e["event"] for e in events)
    print(f"事件类型分布: {dict(type_counts)}")
    print("-" * 70)

    # 模拟前端累积
    frontend_content = ""
    frontend_reasoning = ""
    frontend_tasks = []

    for i, e in enumerate(events):
        et = e["event"]
        d = e["data"]

        if et == "content":
            text = d.get("content", "")
            frontend_content += text
            print(f"[{i:3d}] {et:12s} +{len(text):4d} chars | {repr(text[:100])}")
        elif et == "reasoning":
            text = d.get("content", "")
            frontend_reasoning += text
            # 只打印前几个和后几个
            if i < 5 or i > len(events) - 5:
                print(f"[{i:3d}] {et:12s} +{len(text):4d} chars | {repr(text[:100])}")
            elif i == 5:
                print(f"      ... (中间 {len(events) - 10} 个事件省略) ...")
        elif et == "task":
            frontend_tasks.append(d)
            print(f"[{i:3d}] {et:12s} type={d.get('type','?')} result={repr(d.get('result','')[:80])}")
        elif et == "done":
            print(f"[{i:3d}] {et:12s} ✓ 完成")
        elif et == "error":
            print(f"[{i:3d}] {et:12s} ❌ {d.get('content', '')[:200]}")
        elif et == "warning":
            print(f"[{i:3d}] {et:12s} ⚠ {d.get('content', '')[:200]}")
        else:
            print(f"[{i:3d}] {et:12s} {json.dumps(d, ensure_ascii=False)[:150]}")

    print("\n" + "=" * 70)
    print("前端累积结果")
    print("=" * 70)

    # 清理 reasoning 中的 think 标记
    clean_reasoning = frontend_reasoning.replace("<THINK_V2>", "").replace("</think>", "").strip()
    clean_content = frontend_content.strip()

    print(f"\n  reasoning 总长度: {len(frontend_reasoning)} chars")
    print(f"  reasoning 清理后: {len(clean_reasoning)} chars")
    print(f"  reasoning 前 300 chars:\n    {repr(clean_reasoning[:300])}")
    print(f"\n  content 总长度: {len(frontend_content)} chars")
    print(f"  content 清理后: {len(clean_content)} chars")
    print(f"  content 前 300 chars:\n    {repr(clean_content[:300])}")
    print(f"  content 后 200 chars:\n    {repr(clean_content[-200:] if len(clean_content) > 200 else clean_content)}")
    print(f"\n  tasks 数量: {len(frontend_tasks)}")

    # 检查 content 中是否含有 <task> 标签
    if "<task>" in clean_content.lower():
        print("\n  ⚠ 警告: content 中仍含有 <task> 标签！")
        # 找出所有出现位置
        idx = clean_content.lower().find("<task>")
        print(f"   首次出现位置: {idx}, 上下文: {repr(clean_content[max(0,idx-20):idx+80])}")
    else:
        print("\n  ✓ content 中不含 <task> 标签")

    # 检查 reasoning 中是否有 think 标记
    if "<THINK_V2>" in frontend_reasoning:
        print("  ✓ reasoning 中包含 THINK_V2 标记（正确）")
    else:
        print("  ⚠ reasoning 中不包含 THINK_V2 标记！")

    # 验证数据库中存储的消息
    print("\n" + "=" * 70)
    print("数据库验证：读取会话消息")
    print("=" * 70)
    try:
        req = urllib.request.Request(
            f"{BASE}/api/sessions/{sid}/messages?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        for msg in data.get("messages", []):
            role = msg["role"]
            content = msg.get("content", "")
            reasoning = msg.get("reasoning_content", "")
            print(f"\n  [{role}] id={msg.get('id')}")
            print(f"    content     : {len(content)} chars, 前80: {repr(content[:80])}")
            print(f"    reasoning   : {len(reasoning)} chars, 前80: {repr(reasoning[:80])}")
            if "<task>" in content.lower():
                print(f"    ⚠ content 含 <task>!")
            if "<task>" in reasoning.lower():
                print(f"    ⚠ reasoning 含 <task>!")
    except Exception as e:
        print(f"  读取消息失败: {e}")

    # 总结
    print("\n" + "=" * 70)
    print("诊断总结")
    print("=" * 70)
    issues = []

    if not clean_reasoning:
        issues.append("reasoning 为空")
    if not clean_content:
        issues.append("content 为空（最终回答缺失）")
    if "<task>" in clean_content.lower():
        issues.append("content 含有 <task> 标签（未正确过滤）")
    if "<THINK_V2>" not in frontend_reasoning:
        issues.append("reasoning 缺少 THINK_V2 标记")

    if issues:
        for issue in issues:
            print(f"  ❌ {issue}")
    else:
        print("  ✓ 所有检查通过！思考过程与最终回答正确分离。")
        print(f"  ✓ reasoning={len(clean_reasoning)} chars (思考过程)")
        print(f"  ✓ content={len(clean_content)} chars (最终回答)")


if __name__ == "__main__":
    main()
