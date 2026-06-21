"""
端到端测试：模拟前端行为，验证思考过程与最终回答的分离。
1. 测试 _filter_task_stream 和 _clean_task_blocks 的过滤正确性
2. 通过 API 发送问题，捕获 SSE 流，模拟前端累积逻辑
"""
import json
import os
import sys
import urllib.request
import uuid

from dotenv import load_dotenv

load_dotenv()
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "agent_config"))

from routers.chat import _filter_task_stream, _clean_task_blocks, _strip_raw_task_arrays


# ==================== 测试1: 单元测试 _filter_task_stream ====================
def test_filter_task_stream():
    """模拟 LLM 流式输出的典型场景"""
    print("=" * 60)
    print("测试1: _filter_task_stream 正确性")
    print("=" * 60)

    # 场景A: 纯任务块
    deltas_a = [
        ("reasoning", "我需要先调用 clarifying_questions 技能。"),
        ("content", "<task>[{\"name\":\"clarifying_questions\",\"query\":\"数据联动怎么用？\"}]</task>"),
    ]
    print("\n场景A: 纯任务块")
    results_a = list(_filter_task_stream(iter(deltas_a)))
    for dt, text in results_a:
        print(f"  [{dt}] {repr(text[:80])}")
    content_a = "".join(t for dt, t in results_a if dt == "content")
    reasoning_a = "".join(t for dt, t in results_a if dt == "reasoning")
    print(f"  -> content_len={len(content_a)}, reasoning_len={len(reasoning_a)}")
    assert content_a == "", f"场景A错误: content 应为空，实际={repr(content_a)}"
    assert reasoning_a == "我需要先调用 clarifying_questions 技能。", f"场景A错误: reasoning不匹配"
    print("  ✓ 通过")

    # 场景B: 任务块 + 文本混合
    deltas_b = [
        ("reasoning", "回答用户问题。"),
        ("content", "<task>[{\"name\":\"temporary_context_management\"}]</task>任务因异常已暂时终止，您可以根据建议继续提问。"),
    ]
    print("\n场景B: 任务块+文本混合")
    results_b = list(_filter_task_stream(iter(deltas_b)))
    for dt, text in results_b:
        print(f"  [{dt}] {repr(text[:80])}")
    content_b = "".join(t for dt, t in results_b if dt == "content")
    reasoning_b = "".join(t for dt, t in results_b if dt == "reasoning")
    print(f"  -> content_len={len(content_b)}, reasoning_len={len(reasoning_b)}")
    assert "任务因异常已暂时终止" in content_b, f"场景B错误: 文本应保留"
    assert "<task>" not in content_b, f"场景B错误: task块应被过滤"
    print("  ✓ 通过")

    # 场景C: 多轮混合（模拟 agent 多轮流）
    deltas_c = [
        # Turn 0: 思考 + task
        ("reasoning", "分析用户问题。"),
        ("content", "<task>[{\"name\":\"knowledge_retrieval\",\"query\":\"数据推送\"}]</task>"),
        # Turn 1: 思考 + 最终回答
        ("reasoning", "根据检索结果回答。"),
        ("content", "数据推送是超星低代码平台的自动化数据连接能力。"),
    ]
    print("\n场景C: 多轮混合（模拟 agent loop）")
    results_c = list(_filter_task_stream(iter(deltas_c)))
    for dt, text in results_c:
        print(f"  [{dt}] {repr(text[:80])}")
    content_c = "".join(t for dt, t in results_c if dt == "content")
    reasoning_c = "".join(t for dt, t in results_c if dt == "reasoning")
    print(f"  -> content_len={len(content_c)}, reasoning_len={len(reasoning_c)}")
    assert "数据推送是超星低代码平台" in content_c, f"场景C错误: 最终回答应保留"
    assert "<task>" not in content_c, f"场景C错误: task块应被过滤"
    assert "分析用户问题" in reasoning_c, f"场景C错误: reasoning应保留"
    assert "根据检索结果回答" in reasoning_c, f"场景C错误: reasoning应保留"
    print("  ✓ 通过")

    # 场景D: 分散在多个 content delta 中的任务块
    deltas_d = [
        ("reasoning", "think"),
        ("content", "<task>[{\"name\""),
        ("content", ":\"knowledge_retrieval\""),
        ("content", ",\"query\":\"测试\"}]</task>"),
        ("content", "最终回答内容。"),
    ]
    print("\n场景D: 分散在多个 delta 中的任务块")
    results_d = list(_filter_task_stream(iter(deltas_d)))
    content_d = "".join(t for dt, t in results_d if dt == "content")
    print(f"  content={repr(content_d)}")
    assert content_d == "最终回答内容。", f"场景D错误: {repr(content_d)}"
    print("  ✓ 通过")

    # 场景E: 单 delta 空 task 块 (<task></task>) - 与 E2E 测试匹配
    deltas_e = [
        ("reasoning", "think about what to do."),
        ("content", "<task></task>"),
    ]
    print("\n场景E: 单 delta 空 task 块 (<task></task>)")
    results_e = list(_filter_task_stream(iter(deltas_e)))
    for dt, text in results_e:
        print(f"  [{dt}] {repr(text[:80])}")
    content_e = "".join(t for dt, t in results_e if dt == "content")
    print(f"  -> content_len={len(content_e)}")
    assert content_e == "", f"场景E错误: content 应为空，实际={repr(content_e)}"
    print("  ✓ 通过")


# ==================== 测试2: 单元测试 _clean_task_blocks ====================
def test_clean_task_blocks():
    print("\n" + "=" * 60)
    print("测试2: _clean_task_blocks 正确性")
    print("=" * 60)

    # 场景: 混合内容
    text = "<task>[{\"name\":\"k\"}]</task>这是最终回答"
    result = _clean_task_blocks(text)
    print(f"  输入: {repr(text[:80])}")
    print(f"  输出: {repr(result[:80])}")
    assert result == "这是最终回答", f"场景错误: {repr(result)}"
    print("  ✓ 通过")

    # 场景: 纯 JSON 数组
    text2 = '[{"name":"knowledge_retrieval","query":"搜索"}]'
    result2 = _clean_task_blocks(text2)
    print(f"  输入: {repr(text2)}")
    print(f"  输出: {repr(result2)}")
    assert result2 == "", f"场景错误: {repr(result2)}"
    print("  ✓ 通过")

    # 场景: 纯文本（无任务块）
    text3 = "这是普通的回答文本，没有任务块。"
    result3 = _clean_task_blocks(text3)
    print(f"  输入: {repr(text3)}")
    print(f"  输出: {repr(result3)}")
    assert result3 == text3, f"场景错误: {repr(result3)}"
    print("  ✓ 通过")


# ==================== 测试3: 端到端 API 测试 ====================
def sse_read_events(response) -> list[dict]:
    """读取 SSE 流并解析事件"""
    events = []
    event_type = ""
    data_str = ""
    
    body = response.read()
    text = body.decode("utf-8", errors="replace")
    lines = text.split("\n")
    
    for line in lines:
        line = line.strip()
        if not line:
            if event_type or data_str:
                events.append({"event": event_type, "data": data_str})
                event_type = ""
                data_str = ""
            continue
        if line.startswith("event: "):
            event_type = line[7:]
        elif line.startswith("data: "):
            data_str = line[6:]
    
    if event_type or data_str:
        events.append({"event": event_type, "data": data_str})
    
    return events


def test_end_to_end():
    print("\n" + "=" * 60)
    print("测试3: 端到端 API 测试")
    print("=" * 60)

    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        print("  ⚠ 缺少 ARK_API_KEY，跳过端到端测试")
        return

    # 注册/登录测试用户
    test_user = f"e2etest_{os.urandom(4).hex()}"
    test_pass = "test1234"
    try:
        # 注册
        req = urllib.request.Request(
            "http://127.0.0.1:8001/api/register",
            data=json.dumps({"username": test_user, "password": test_pass}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        reg_data = json.loads(resp.read())
        if reg_data.get("ok"):
            print(f"  注册测试用户 {test_user} 成功")
        else:
            print(f"  注册返回: {reg_data}")
    except Exception as e:
        print(f"  注册异常: {e}")
    
    # 登录
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8001/api/login",
            data=json.dumps({"username": test_user, "password": test_pass}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        login_data = json.loads(resp.read())
        token = login_data.get("access_token", "")
        if not token:
            print(f"  ⚠ 登录返回无 token: {login_data}")
            return
        print(f"  登录成功，获取 token")
    except Exception as e:
        print(f"  ⚠ 登录失败 ({e})")
        return

    auth_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # 创建 session
    req = urllib.request.Request(
        "http://127.0.0.1:8001/api/chat",
        data=json.dumps({"session_id": "", "message": "", "new_session": True}).encode(),
        headers=auth_headers,
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        sid = resp.headers.get("X-Session-Id", "")
        resp.read()
        print(f"  创建 session: {sid}")
    except Exception as e:
        print(f"  ⚠ 无法连接后端 ({e})")
        return

    # 发送问题
    question = "数据联动怎么用？"
    print(f"  发送问题: {question}")
    
    req = urllib.request.Request(
        "http://127.0.0.1:8001/api/chat",
        data=json.dumps({"session_id": sid, "message": question, "new_session": False}).encode(),
        headers=auth_headers,
        method="POST",
    )
    
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        events = sse_read_events(resp)
    except Exception as e:
        print(f"  ⚠ 请求失败: {e}")
        return

    # 模拟前端行为：累积内容
    frontend_content = ""
    frontend_reasoning = ""
    frontend_tasks = []
    content_events = []
    reasoning_events = []

    for evt in events:
        event_type = evt.get("event", "")
        data_str = evt.get("data", "")
        
        if event_type == "done":
            break
        
        if data_str == "{}":
            continue
        
        try:
            data = json.loads(data_str)
        except:
            continue

        if event_type == "content":
            t = data.get("content", "")
            frontend_content += t
            content_events.append(t)
        elif event_type == "reasoning":
            t = data.get("content", "")
            frontend_reasoning += t
            reasoning_events.append(t)
        elif event_type == "task":
            frontend_tasks.append({"type": data.get("type", ""), "result": data.get("result", "")})

    print(f"\n  --- SSE 事件详情 ---")
    print(f"  reasoning events: {len(reasoning_events)}")
    print(f"  content events: {len(content_events)}")
    if content_events:
        print(f"  前5个 content 事件:")
        for i, ce in enumerate(content_events[:5]):
            print(f"    [{i}] len={len(ce)} {repr(ce)}")

    print(f"\n  --- 前端最终状态 ---")
    print(f"  reasoning ({len(frontend_reasoning)} chars): {repr(frontend_reasoning[:200])}")
    print(f"  content ({len(frontend_content)} chars): {repr(frontend_content[:200])}")
    print(f"  tasks: {len(frontend_tasks)}")
    print(f"  total events: {len(events)}")

    # 验证
    issues = []
    if not frontend_content:
        issues.append("content 为空，消息气泡无内容！")
    if "<task>" in frontend_content.lower() or "[{" in frontend_content:
        issues.append("content 包含任务块，未正确过滤！")
    if not frontend_reasoning:
        issues.append("reasoning 为空，思考过程丢失！")
    
    if issues:
        print(f"\n  ⚠ 发现问题:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print(f"\n  ✓ 端到端测试通过！思考过程与最终回答正确分离。")

    # 检查数据库存储
    try:
        import sqlite3
        db_path = os.path.join(PROJECT_ROOT, "backend", "data", "app.db")
        if not os.path.exists(db_path):
            db_path = os.environ.get("DB_PATH", db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        msgs = conn.execute(
            "SELECT role, content, reasoning_content FROM messages WHERE session_id = ? AND role = 'assistant' ORDER BY id",
            (sid,),
        ).fetchall()
        conn.close()
        
        print(f"\n  --- 数据库中的 assistant 消息 ---")
        print(f"  共 {len(msgs)} 条 assistant 消息")
        for i, msg in enumerate(msgs):
            print(f"  消息{i}: content_len={len(msg['content'])}, reasoning_len={len(msg.get('reasoning_content') or '')}")
            if msg['content']:
                print(f"    content预览: {msg['content'][:100]}...")
            else:
                print(f"    content为空!")
        
        if len(msgs) > 1:
            print(f"  ⚠ 数据库中有 {len(msgs)} 条 assistant 消息，但应该只有 1 条！")
        elif len(msgs) == 0:
            print(f"  ⚠ 数据库中没有 assistant 消息！")
    except Exception as e:
        print(f"  无法读取数据库: {e}")


if __name__ == "__main__":
    # 运行单元测试
    test_filter_task_stream()
    test_clean_task_blocks()
    
    # 运行端到端测试
    test_end_to_end()
    
    print("\n" + "=" * 60)
    print("所有测试完成")
    print("=" * 60)
