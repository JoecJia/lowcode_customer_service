import asyncio
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# 兼容两种启动方式：
#   1) python backend/main.py                → backend/ 已在 sys.path
#   2) python -m uvicorn backend.main:app    → 需要手动补 backend/，
#      否则 routers / services / dependencies 等包会导入失败
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
for _path in (_BACKEND_DIR, os.path.join(os.path.dirname(_BACKEND_DIR), "agent_config")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from routers.chat import router as chat_router
from routers.auth import router as auth_router
from routers.feedback import router as feedback_router
from routers.admin import router as admin_router
from services.mcp_service import mcp_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动 MCP Client：连接失败自动降级，不影响其他能力
    await mcp_manager.start()

    # 预热知识检索：首次构建检索器需约 11 秒（全语料 jieba 分词 + 构建 BM25Okapi
    # + 加载 FAISS 索引与 embedding 模型）。提前到启动阶段完成，避免首个用户请求承担。
    # 该过程是 CPU 密集型同步操作，放入线程执行以免阻塞事件循环。
    try:
        from services.search_service import prewarm

        stats = await asyncio.to_thread(prewarm)
        print(
            f"[startup] 知识检索预热完成：ready={stats['ready']} "
            f"耗时 {stats['elapsed_ms']:.0f}ms",
            file=sys.stderr,
            flush=True,
        )
    except Exception as exc:
        print(f"[startup] 知识检索预热失败（不影响服务启动）：{exc}", file=sys.stderr, flush=True)

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


# 图片类静态资源：文件名通常是内容哈希，内容不可变，可长期缓存
_CACHEABLE_ASSET_SUFFIXES = (".png", ".gif", ".jpg", ".jpeg", ".webp", ".svg", ".ico")


@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/"):
        if path.lower().endswith(_CACHEABLE_ASSET_SUFFIXES):
            # 知识库图片（agent_config/context/assets/）：内容不可变 → 长期缓存。
            # 原先统一设 no-store，导致流式渲染重建 <img> 时每次都要重新下载整张图。
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            # 前端构建产物（frontend/dist/assets/*.js|css）：保持禁用缓存，
            # 确保前端更新后用户立即拿到新文件
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
    """存活检查：进程能响应即返回 ok，不校验检索链路。"""
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """就绪检查：校验检索链路是否完整可用（含向量通道）。

    与 /health 的区别：检索降级时返回 503。典型场景是 embedding 模型不在本地缓存，
    HybridSearcher 会吞掉异常并把向量通道置空，混合检索静默退化为纯 BM25——
    线上表现为「检索不准、模型反复换关键词重试、响应变慢」，很难从别处察觉。
    """
    from services.search_service import retrieval_status

    stats = retrieval_status()
    healthy = bool(stats.get("initialized") and stats.get("vector_ready"))
    payload = {"status": "ok" if healthy else "degraded", **stats}
    if not healthy:
        payload["hint"] = (
            "向量检索不可用（已降级为纯 BM25）。"
            "请在服务器上执行 python debug/download_embedding_model.py 后重启服务。"
        )
        return JSONResponse(status_code=503, content=payload)
    return payload


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
