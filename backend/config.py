import os

from dotenv import load_dotenv

load_dotenv()

ARK_CHAT_COMPLETIONS_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

MAX_AGENT_TURNS = 6
MAX_TASK_CALLS = 10

DEBUG = os.environ.get("ARK_DEBUG", "").strip().lower() in {"1", "true", "yes"}

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "1800"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(REPO_DIR, "data", "app.db"))

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
