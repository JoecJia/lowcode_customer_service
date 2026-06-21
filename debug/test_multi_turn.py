"""测试多轮 agent 场景下的思考/回答分离"""
import json
import os
import urllib.request
import urllib.error
from collections import Counter

from dotenv import load_dotenv
load_dotenv()

BASE = "http://127.0.0.1:8001"


def login(username="diagnose_test", password="test1234"):
    req = urllib.request.Request(
        f"{BASE}/api/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read()).get("access_token", "")


def create_session(token):
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=json.dumps({"session_id": "", "message": "", "new_session": True}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST")
    resp = urllib.request.urlopen(req, timeout=10)
    sid = resp.headers.get("X-Session-Id", "")
    resp.read()
    return sid


def chat_and_parse(token, sid, message):
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=json.dumps({"session_id": sid, "message": message, "new_session": False}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST")
    resp = urllib.request.urlopen(req, timeout=300)
    body = resp.read().decode("utf-8", errors="replace")

    events = []
    lines = body.split("\n")
    et, ds = "", ""
    for ln in lines:
        ln = ln.strip()
        if not ln:
            if et or ds:
                try:
                    d = json.loads(ds) if ds and ds != "{}" else {}
                except:
                    d = {"_raw": ds}
                events.append({"event": et, "data": d})
                et, ds = "", ""
            continue
        if ln.startswith("event: "):
            et = ln[7:]
        elif ln.startswith("data: "):
            ds = ln[6:]
    if et or ds:
        try:
            d = json.loads(ds) if ds and ds != "{}" else {}
        except:
            d = {"_raw": ds}
        events.append({"event": et, "data": d})
    return events


def main():
    print("=" * 70)
    print("多轮 agent 测试：搭建资产管理系统")
    print("=" * 70)

    token = login()
    sid = create_session(token)
    print(f"Session: {sid}")

    question = "帮我搭建一个资产管理系统，只有一个管理员角色，要实现资产的入库、出库和盘点"
    print(f"Question: {question}")

    print("\n[1] 发送请求...")
    try:
        events = chat_and_parse(token, sid, question)
    except Exception as e:
        print(f"   错误: {e}")
        return

    # 统计
    types = Counter(e["event"] for e in events)
    print(f"\n[2] 事件统计: {dict(types)}")

    # 模拟前端累积
    frontend_content = ""
    frontend_reasoning = ""
    tasks = []

    last_reasoning_end = 0
    last_content_end = 0

    for i, e in enumerate(events):
        et = e["event"]
        d = e["data"]
        if et == "content":
            frontend_content += d.get("content", "")
            last_content_end = i
        elif et == "reasoning":
            frontend_reasoning += d.get("content", "")
            last_reasoning_end = i
        elif et == "task":
            tasks.append(d)
            print(f"  [task #{len(tasks)}] type={d.get('type','?')} "
                  f"result_len={len(d.get('result',''))}")

    # 显示 reasoning 区域
    clean_reason = frontend_reasoning.replace("<THINK_V2>", "").replace("</think>", "").strip()
    clean_cont = frontend_content.strip()

    print(f"\n[3] 最终 reasoning: {len(clean_reason)} chars")
    print(f"    前 300: {repr(clean_reason[:300])}")
    print(f"\n[4] 最终 content: {len(clean_cont)} chars")
    print(f"    前 300: {repr(clean_cont[:300])}")
    print(f"    后 200: {repr(clean_cont[-200:] if len(clean_cont) > 200 else clean_cont)}")

    # 检查
    has_task_in_content = "<task>" in clean_cont.lower() or "</task>" in clean_cont.lower()
    print(f"\n[5] content 含 <task>: {has_task_in_content}")

    if has_task_in_content:
        print("  ⚠ 问题: content 中有 task 标签!")
        idx = clean_cont.lower().find("<task>")
        if idx >= 0:
            print(f"    位置 {idx}: {repr(clean_cont[max(0,idx-30):idx+100])}")

    # 检查 reasoning 中的 think 标签
    if "<THINK_V2>" in frontend_reasoning or "</think>" in frontend_reasoning:
        print("  ✓ reasoning 含 think 标记")

    # DB 验证
    try:
        req = urllib.request.Request(
            f"{BASE}/api/sessions/{sid}/messages?limit=20",
            headers={"Authorization": f"Bearer {token}"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())

        print(f"\n[6] DB 消息验证:")
        for msg in data.get("messages", []):
            r = msg["role"]
            c = msg.get("content", "")
            rc = msg.get("reasoning_content", "")
            is_hidden = r == "user" and c.startswith("<task_result>")
            if is_hidden:
                print(f"  [{r}] (hidden task_result) id={msg.get('id')} content_len={len(c)}")
            else:
                print(f"  [{r}] id={msg.get('id')} "
                      f"content_len={len(c)} reasoning_len={len(rc)}")
                if "<task>" in c.lower():
                    print(f"    ⚠ content 含 <task>!")
    except Exception as e:
        print(f"  读取消息失败: {e}")

    print("\n" + "=" * 70)
    if has_task_in_content:
        print("❌ FAIL: content 含有 task 标签")
    elif not clean_cont:
        print("❌ FAIL: content 为空")
    else:
        print("✓ PASS: 思考过程与最终回答已正确分离")
    print("=" * 70)


if __name__ == "__main__":
    main()
