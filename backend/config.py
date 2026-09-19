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

# ── 超星 Passport 登录 ──
# 接口域名（passport2-api 为官方文档统一域名；自检脚本可实测切换）
PASSPORT_BASE_URL = os.environ.get("PASSPORT_BASE_URL", "https://passport2-api.chaoxing.com/")
if not PASSPORT_BASE_URL.endswith("/"):
    PASSPORT_BASE_URL += "/"

# 超星登录页（未登录时引导跳转，refer 由前端拼接为本站地址）
PASSPORT_LOGIN_URL = os.environ.get("PASSPORT_LOGIN_URL", "https://passport2.chaoxing.com/login")

# 应用凭证（向 passport 方申请获得）
PASSPORT_APP_ID = os.environ.get("PASSPORT_APP_ID", "")
PASSPORT_APP_KEY_PROD = os.environ.get("PASSPORT_APP_KEY", "")
PASSPORT_APP_KEY_DEBUG = os.environ.get("PASSPORT_APP_KEY_DEBUG", "")
# prod：生产环境；debug：开发环境（VPN / 办公区 IP）
PASSPORT_KEY_MODE = os.environ.get("PASSPORT_KEY_MODE", "prod").strip().lower()
PASSPORT_APP_KEY = PASSPORT_APP_KEY_DEBUG if PASSPORT_KEY_MODE == "debug" else PASSPORT_APP_KEY_PROD

# 固定密钥（passport 方提供）
PASSPORT_API_USERINFO_KEY = os.environ.get("PASSPORT_API_USERINFO_KEY", "")
PASSPORT_VC3_AES_KEY = os.environ.get("PASSPORT_VC3_AES_KEY", "")

# VC3 验签 MD5 密钥（运行时优先取接口返回值，此处为兜底）
PASSPORT_MD5_KEY = os.environ.get("PASSPORT_MD5_KEY", "")
PASSPORT_SIMULATE_MD5_KEY = os.environ.get("PASSPORT_SIMULATE_MD5_KEY", "")

# 是否向 passport 透传客户端 IP / UA（官方文档要求，联调失败可关闭）
PASSPORT_FORWARD_CLIENT_INFO = os.environ.get(
    "PASSPORT_FORWARD_CLIENT_INFO", "true"
).strip().lower() in {"1", "true", "yes"}

# 允许的跨域来源（CORS 白名单，逗号分隔）
APP_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("APP_ORIGINS", "https://service.cxlowcode.com").split(",")
    if origin.strip()
]
