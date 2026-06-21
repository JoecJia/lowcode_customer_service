"""快速验证：检查后端是否使用最新代码"""
import json
import os
import urllib.request

from dotenv import load_dotenv

load_dotenv()

# Register + login
test_user = f"quicktest_{os.urandom(4).hex()}"
test_pass = "test1234"

# Register
req = urllib.request.Request(
    "http://127.0.0.1:8001/api/register",
    data=json.dumps({"username": test_user, "password": test_pass}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    urllib.request.urlopen(req, timeout=10).read()
except Exception:
    pass

# Login
req = urllib.request.Request(
    "http://127.0.0.1:8001/api/login",
    data=json.dumps({"username": test_user, "password": test_pass}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
resp = urllib.request.urlopen(req, timeout=10)
token = json.loads(resp.read())["access_token"]
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

# Create session
req = urllib.request.Request(
    "http://127.0.0.1:8001/api/chat",
    data=json.dumps({"session_id": "", "message": "", "new_session": True}).encode(),
    headers=headers,
    method="POST",
)
resp = urllib.request.urlopen(req, timeout=10)
sid = resp.headers["X-Session-Id"]
resp.read()

# Send "你好" - quick reply
req = urllib.request.Request(
    "http://127.0.0.1:8001/api/chat",
    data=json.dumps({"session_id": sid, "message": "你好", "new_session": False}).encode(),
    headers=headers,
    method="POST",
)
resp = urllib.request.urlopen(req, timeout=60)
raw = resp.read().decode("utf-8", errors="replace")

print("=== Has THINK_V2:", "THINK_V2" in raw)
print("=== Has <think>:", "<think>" in raw)
print("=== Has <task>:", "<task>" in raw)

# Show content events
for line in raw.split("\n"):
    if "event: content" in line or "event: reasoning" in line:
        continue
    if line.startswith("data: "):
        data = line[6:]
        if data == "{}":
            continue
        try:
            d = json.loads(data)
            c = d.get("content", "")
            if c:
                prefix = "THINK_V2" if c == "THINK_V2" else c[:60]
                print(f"  content chunk: {repr(prefix)}...")
        except:
            pass
