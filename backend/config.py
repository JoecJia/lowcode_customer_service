import os

from dotenv import load_dotenv

load_dotenv(override=True)

ARK_CHAT_COMPLETIONS_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

MAX_AGENT_TURNS = 6
MAX_TASK_CALLS = 10

DEBUG = os.environ.get("ARK_DEBUG", "").strip().lower() in {"1", "true", "yes"}

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "1800"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(REPO_DIR, "data", "app.db"))

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")

# ── MCP 配置 ──
# mcp_servers.json 位于 backend/ 目录下
MCP_SERVERS_PATH = os.environ.get(
    "MCP_SERVERS_PATH",
    os.path.join(REPO_DIR, "mcp_servers.json"),
)
# 单次 MCP 工具调用超时（秒）
MCP_CALL_TIMEOUT_SECONDS = int(os.environ.get("MCP_CALL_TIMEOUT_SECONDS", "60"))

# ── Chaoxing MCP token（凭据来自 .env，已 gitignore）──
CHAOXING_MCP_TOKEN_URL = os.environ.get("CHAOXING_MCP_TOKEN_URL", "")
CHAOXING_MCP_TYPE = os.environ.get("CHAOXING_MCP_TYPE", "forms_config_mcp")
CHAOXING_MCP_FID = os.environ.get("CHAOXING_MCP_FID", "")
CHAOXING_MCP_UID = os.environ.get("CHAOXING_MCP_UID", "")
CHAOXING_MCP_SIGN = os.environ.get("CHAOXING_MCP_SIGN", "")
CHAOXING_MCP_KEY = os.environ.get("CHAOXING_MCP_KEY", "")
