import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent_config"))

from routers.chat import router as chat_router
from routers.auth import router as auth_router
from routers.feedback import router as feedback_router
from routers.admin import router as admin_router
from services.mcp_service import mcp_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动 MCP Client：连接失败自动降级，不影响其他能力
    await mcp_manager.start()
    yield
    await mcp_manager.close()


app = FastAPI(title="低代码智能客服", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    # 静态资源禁用缓存，确保前端更新后立即生效
    if request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(feedback_router)
app.include_router(admin_router)

@app.get("/health")
async def health():
    return {"status": "ok"}


# 挂载知识库图片资源：agent_config/context/assets/ → /assets/
context_assets = os.path.join(os.path.dirname(__file__), "..", "agent_config", "context", "assets")
if os.path.isdir(context_assets):
    app.mount("/assets", StaticFiles(directory=context_assets), name="context_assets")

# 挂载前端：SPA 模式 —— 非 API 路径回退到 index.html
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # 先检查是否是真实存在的静态文件
        file_path = os.path.join(frontend_dist, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        # 其余路径（包括 SPA 路由如 /admin, /admin/login）统一返回 index.html
        return FileResponse(os.path.join(frontend_dist, "index.html"))


if __name__ == "__main__":
    import uvicorn

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
