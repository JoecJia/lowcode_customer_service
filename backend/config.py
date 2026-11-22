import os

from dotenv import load_dotenv

load_dotenv(override=True)

ARK_CHAT_COMPLETIONS_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

# Agent 循环上限；支持环境变量覆盖（便于复现/验证异常退出分支）
MAX_AGENT_TURNS = int(os.environ.get("MAX_AGENT_TURNS", "6"))
MAX_TASK_CALLS = int(os.environ.get("MAX_TASK_CALLS", "10"))
# 重复调用检测：同一个任务（类型 + query + 参数完全一致）允许的最大执行次数
MAX_IDENTICAL_TASK_CALLS = int(os.environ.get("MAX_IDENTICAL_TASK_CALLS", "1"))
# 重复调用检测：同一个技能（忽略 query）允许的最大调用次数，
# 用于兜住「不断改写关键词反复检索同一个技能」的情况
MAX_SAME_SKILL_CALLS = int(os.environ.get("MAX_SAME_SKILL_CALLS", "3"))

DEBUG = os.environ.get("ARK_DEBUG", "").strip().lower() in {"1", "true", "yes"}

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 多模态模型与附件配置 ──
# doubao-seed-2-0-pro-260215 于 2026-11-24 14:00 EOS，默认使用官方建议迁移模型
ARK_VISION_MODEL = os.environ.get("ARK_VISION_MODEL", "doubao-seed-2-1-lite-260915")
ARK_TEXT_MODEL = os.environ.get("ARK_TEXT_MODEL", "doubao-seed-2-1-lite-260915")
ARK_IMAGE_DETAIL = os.environ.get("ARK_IMAGE_DETAIL", "high")

UPLOAD_DIR = os.environ.get(
    "UPLOAD_DIR",
    os.path.join(REPO_DIR, "data", "uploads"),
)
MAX_IMAGE_SIZE = int(os.environ.get("MAX_IMAGE_SIZE", str(10 * 1024 * 1024)))
MAX_PDF_SIZE = int(os.environ.get("MAX_PDF_SIZE", str(20 * 1024 * 1024)))
MAX_ATTACHMENTS_TOTAL_SIZE = int(
    os.environ.get("MAX_ATTACHMENTS_TOTAL_SIZE", str(20 * 1024 * 1024))
)
MAX_ATTACHMENTS_COUNT = int(os.environ.get("MAX_ATTACHMENTS_COUNT", "6"))
ATTACHMENT_RETENTION_DAYS = int(os.environ.get("ATTACHMENT_RETENTION_DAYS", "30"))

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
