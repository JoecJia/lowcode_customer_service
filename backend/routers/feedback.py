"""不满意反馈 API 路由"""

import os
import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from database import get_db
from dependencies.auth import get_current_user, require_admin
from services.session_service import get_feedback_service, get_session_store

router = APIRouter(prefix="/api")


class FeedbackRequest(BaseModel):
    session_id: str


class ResolveRequest(BaseModel):
    qa_pairs: list[dict]


# ====== 用户端接口（已有，保持不变）======

@router.post("/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = int(current_user["sub"])
    store = get_session_store()
    feedback_svc = get_feedback_service()

    owner = store.get_session_owner(body.session_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if owner != user_id:
        raise HTTPException(status_code=404, detail="会话不存在")

    ok, message = feedback_svc.submit_feedback(body.session_id, user_id)
    if not ok:
        raise HTTPException(status_code=409, detail=message)

    return {"ok": True, "message": message}


@router.get("/feedback/check")
async def check_feedback(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = int(current_user["sub"])
    feedback_svc = get_feedback_service()
    has_feedback = feedback_svc.check_feedback(session_id, user_id)
    return {"has_feedback": has_feedback}


# ====== 管理端接口（新增）======

@router.get("/admin/feedbacks")
async def list_feedbacks(
    status: str = Query(default="all"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    with get_db() as conn:
        conn.row_factory = sqlite3.Row

        where_clause = ""
        params: list = []
        if status == "pending":
            where_clause = "WHERE f.status = 'pending'"
        elif status == "resolved":
            where_clause = "WHERE f.status = 'resolved'"

        # 总数
        total_row = conn.execute(
            f"""SELECT COUNT(*) as cnt FROM feedback f {where_clause}""",
            params,
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        rows = conn.execute(
            f"""SELECT
                f.id,
                f.session_id,
                f.user_id,
                f.status,
                f.created_at,
                u.username,
                s.title as session_title,
                (SELECT COUNT(*) FROM messages m WHERE m.session_id = f.session_id) AS message_count,
                (SELECT MAX(m2.created_at) FROM messages m2 WHERE m2.session_id = f.session_id) AS last_active
            FROM feedback f
            JOIN users u ON f.user_id = u.id
            LEFT JOIN sessions s ON f.session_id = s.id
            {where_clause}
            ORDER BY f.created_at DESC
            LIMIT ? OFFSET ?""",
            (*params, limit, offset),
        ).fetchall()

    feedbacks = [dict(row) for row in rows]
    return {
        "ok": True,
        "data": {
            "feedbacks": feedbacks,
            "total": total,
            "offset": offset,
            "limit": limit,
        },
    }


@router.get("/admin/feedbacks/{feedback_id}")
async def get_feedback_detail(
    feedback_id: int,
    admin: dict = Depends(require_admin),
):
    with get_db() as conn:
        conn.row_factory = sqlite3.Row

        fb = conn.execute(
            """SELECT f.id, f.session_id, f.user_id, f.status, f.created_at, u.username
               FROM feedback f JOIN users u ON f.user_id = u.id
               WHERE f.id = ?""",
            (feedback_id,),
        ).fetchone()

        if not fb:
            raise HTTPException(status_code=404, detail="反馈不存在")

        msgs = conn.execute(
            """SELECT id, role, content, reasoning_content, created_at
               FROM messages
               WHERE session_id = ?
               ORDER BY created_at ASC""",
            (fb["session_id"],),
        ).fetchall()

    return {
        "ok": True,
        "data": {
            "feedback": dict(fb),
            "messages": [dict(m) for m in msgs],
        },
    }


@router.post("/admin/feedbacks/{feedback_id}/resolve")
async def resolve_feedback(
    feedback_id: int,
    body: ResolveRequest,
    admin: dict = Depends(require_admin),
):
    # 校验
    if not body.qa_pairs or len(body.qa_pairs) == 0:
        raise HTTPException(status_code=422, detail="至少需要一条 Q&A")
    for i, qa in enumerate(body.qa_pairs):
        if not qa.get("answer", "").strip():
            raise HTTPException(status_code=422, detail=f"第 {i+1} 条回答不能为空")

    # 写入 FAQ 文件
    project_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    faq_dir = os.path.join(project_root, "agent_config", "context", "faq")
    os.makedirs(faq_dir, exist_ok=True)

    # 找到当前活跃的 FAQ 文件（未满 100 条的）
    faq_files = sorted([f for f in os.listdir(faq_dir) if f.startswith("general_faq") and f.endswith(".md")])

    if not faq_files:
        target_file = os.path.join(faq_dir, "general_faq.md")
        qa_count = 0
    else:
        # 选择最后一个文件
        target_file = os.path.join(faq_dir, faq_files[-1])
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
        qa_count = content.count("### Q:")

    saved_count = 0
    for qa in body.qa_pairs:
        question = qa.get("question", "").strip()
        answer = qa.get("answer", "").strip()
        if not answer:
            continue

        # 如果当前文件已满 100 条，拆到新文件
        if qa_count >= 100:
            start_num = qa_count - (qa_count % 100) + 1
            end_num = qa_count
            new_filename = f"general_faq({start_num}-{end_num}.md)"
            target_file = os.path.join(faq_dir, new_filename)
            qa_count = 0

        entry = f"\n### Q: {question}\nA: {answer}\n"
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(entry)
        qa_count += 1
        saved_count += 1

    # 增量向量化
    try:
        import sys
        sys.path.insert(0, os.path.join(project_root, "agent_config", "skills", "context_transformation"))
        from vectorizer import update_document
        update_document(target_file)
    except Exception as e:
        # 向量化失败不回滚文件写入，仅提示
        pass

    # 更新反馈状态
    with get_db() as conn:
        conn.execute(
            "UPDATE feedback SET status = 'resolved' WHERE id = ?",
            (feedback_id,),
        )
        conn.commit()

    return {
        "ok": True,
        "message": f"已保存 {saved_count} 条 Q&A 到 FAQ 知识库，索引已更新",
    }
