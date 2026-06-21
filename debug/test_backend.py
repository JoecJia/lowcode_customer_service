"""后端迁移验证脚本 — 测试所有 import 和关键路径"""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")


def green(text):
    return f"\033[32m{text}\033[0m"


def red(text):
    return f"\033[31m{text}\033[0m"


def yellow(text):
    return f"\033[33m{text}\033[0m"


def run_test(name, code):
    print(f"  {name} ...", end=" ")
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=15,
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONPATH": BACKEND_DIR},
        )
        if result.returncode == 0:
            print(green("PASS"))
        else:
            print(red(f"FAIL (exit {result.returncode})"))
            for line in result.stderr.strip().split("\n")[-5:]:
                print(f"       {line}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(red("TIMEOUT"))
        return False
    except Exception as e:
        print(red(f"ERROR: {e}"))
        return False


def main():
    print("=" * 60)
    print("  后端迁移验证")
    print("=" * 60)
    print(f"  项目根目录: {PROJECT_ROOT}")
    print(f"  后端目录:   {BACKEND_DIR}")
    print()

    results = []

    # 1. 目录结构检查
    print(yellow("[1/6] 目录结构检查"))
    checks = [
        ("backend/ 目录存在", os.path.isdir(BACKEND_DIR)),
        ("backend/main.py 存在", os.path.isfile(os.path.join(BACKEND_DIR, "main.py"))),
        ("backend/config.py 存在", os.path.isfile(os.path.join(BACKEND_DIR, "config.py"))),
        ("backend/routers/ 存在", os.path.isdir(os.path.join(BACKEND_DIR, "routers"))),
        ("backend/services/ 存在", os.path.isdir(os.path.join(BACKEND_DIR, "services"))),
        ("agent_config/ 目录存在", os.path.isdir(os.path.join(PROJECT_ROOT, "agent_config"))),
        ("agent_config/skills/ 存在", os.path.isdir(os.path.join(PROJECT_ROOT, "agent_config", "skills"))),
        ("agent_config/context/ 存在", os.path.isdir(os.path.join(PROJECT_ROOT, "agent_config", "context"))),
        ("根目录无 main.py", not os.path.isfile(os.path.join(PROJECT_ROOT, "main.py"))),
        ("根目录无 routers/", not os.path.isdir(os.path.join(PROJECT_ROOT, "routers"))),
        ("根目录无 services/", not os.path.isdir(os.path.join(PROJECT_ROOT, "services"))),
    ]
    for name, ok in checks:
        status = green("OK") if ok else red("MISSING")
        print(f"    [{status}] {name}")
        results.append((name, ok))
    print()

    # 2. config import
    print(yellow("[2/6] Import: config"))
    ok = run_test("config", """
import sys; sys.path.insert(0, "backend")
from config import ARK_CHAT_COMPLETIONS_URL, MAX_AGENT_TURNS, REPO_DIR, DB_PATH, SESSION_TTL_SECONDS
assert REPO_DIR.endswith("backend"), f"REPO_DIR should end with backend, got {REPO_DIR}"
assert ARK_CHAT_COMPLETIONS_URL.startswith("https"), "Invalid ARK_CHAT_COMPLETIONS_URL"
print(f"  REPO_DIR={REPO_DIR}")
print(f"  DB_PATH={DB_PATH}")
""")
    results.append(("config import", ok))
    print()

    # 3. services import
    print(yellow("[3/6] Import: services"))
    ok = run_test("services", """
import sys; sys.path.insert(0, "backend")
from services.llm_service import build_ssl_context, parse_tasks, read_text_file, stream_chat_completions
from services.session_service import get_session_store
from services.skill_service import dispatch_skill, format_task_result, get_system_messages, SKILL_REGISTRY
print(f"  Skills registered: {len(SKILL_REGISTRY)}")
print(f"  Session store: OK")
""")
    results.append(("services import", ok))
    print()

    # 4. routers import
    print(yellow("[4/6] Import: routers"))
    ok = run_test("routers", """
import sys; sys.path.insert(0, "backend")
from routers.chat import router
print(f"  Router prefix: {router.prefix}")
print(f"  Routes: {[r.path for r in router.routes]}")
""")
    results.append(("routers import", ok))
    print()

    # 5. FastAPI app creation
    print(yellow("[5/6] FastAPI 应用创建"))
    ok = run_test("app creation", """
import sys; sys.path.insert(0, "backend")
from main import app
assert app.title == "低代码智能客服", f"Title mismatch: {app.title}"
routes = [r.path for r in app.routes]
print(f"  App title: {app.title}")
print(f"  Routes: {routes}")
assert "/health" in routes, "Missing /health route"
assert "/api/chat" in routes, "Missing /api/chat route"
assert "/api/sessions" in routes, "Missing /api/sessions route"
""")
    results.append(("FastAPI app", ok))
    print()

    # 6. Path resolution
    print(yellow("[6/6] 关键路径校验"))
    ok = run_test("paths", """
import os, sys; sys.path.insert(0, "backend")
from config import REPO_DIR, DB_PATH
from services.skill_service import get_system_messages

# DB_PATH should be under backend/
assert os.path.dirname(DB_PATH) == os.path.join(REPO_DIR, "data"), f"DB_PATH mismatch: {DB_PATH}"
print(f"  DB_PATH={DB_PATH}")

# Check agent.md exists (for get_system_messages)
agent_md = os.path.join(os.path.dirname(REPO_DIR), "agent_config", "agent.md")
assert os.path.isfile(agent_md), f"agent.md not found at {agent_md}"
print(f"  agent.md found at {agent_md}")

# Check skills exist
for skill_name, skill_rel in [
    ("knowledge_retrieval", "../agent_config/skills/knowledge_retrieval/knowledge_retrieval.md"),
    ("clarifying_questions", "../agent_config/skills/clarifying_questions.md"),
]:
    full = os.path.join(REPO_DIR, skill_rel)
    assert os.path.isfile(full), f"{skill_name} not found at {full}"
print(f"  Skills files: OK")

# Check frontend dist path
frontend_dist = os.path.join(os.path.dirname(REPO_DIR), "frontend", "dist")
print(f"  frontend/dist: {frontend_dist} (exists={os.path.isdir(frontend_dist)})")

# Check system messages load
messages = get_system_messages()
assert len(messages) == 2, f"Expected 2 system messages, got {len(messages)}"
print(f"  System messages loaded: {len(messages)} (first {len(messages[0]['content'])} chars)")
""")
    results.append(("path resolution", ok))
    print()

    # Summary
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    if passed == total:
        print(green(f"  全部通过! ({passed}/{total})"))
        return 0
    else:
        print(red(f"  {total - passed} 项失败 ({passed}/{total})"))
        for name, ok in results:
            if not ok:
                print(f"    FAIL: {name}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
