"""后台维护助手的 Context 受控写入服务。

职责（见 docs/dev_docs/04_双智能体拆分.md §11 / §13）：
- context_editor 受控工具：list / read / stage_write / list_changes
- 会话批次：一次对话的多文件修改归入同一 pending 批次
- apply_batch：预检 → 备份 → 写入 → 进程内索引 → 单事务日志（全程 _BATCH_LOCK）
- rollback_batch：全量校验 → 原子还原 → 索引 → 新 rolled_back 批次（同锁）
"""
import asyncio
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from config import REPO_DIR
from database import get_db
from services.llm_service import Task
from services.skill_service import SkillResult

# agent_config 目录（知识库根）
AGENT_CONFIG_DIR = os.path.realpath(os.path.join(REPO_DIR, "..", "agent_config"))
CONTEXT_DIR = os.path.join(AGENT_CONFIG_DIR, "context")
STAGING_DIR = os.path.join(CONTEXT_DIR, ".staging")
BACKUP_DIR = os.path.join(CONTEXT_DIR, ".backup")

# 并发锁：_BATCH_LOCK 覆盖 apply/rollback 全程，_INDEX_LOCK 仅保护索引本身
_BATCH_LOCK = asyncio.Lock()
_INDEX_LOCK = asyncio.Lock()
_prewarm_lock = asyncio.Lock()
_background_tasks: set[asyncio.Task] = set()

# 灰度开关与 TTL（从环境变量读取，默认关闭/24h）
ENABLE_ADMIN_AGENT = os.environ.get("ENABLE_ADMIN_AGENT", "0").strip().lower() in {"1", "true", "yes"}
try:
    STAGING_TTL_SECONDS = int(os.environ.get("CONTEXT_STAGING_TTL_SECONDS", "86400"))
except ValueError:
    STAGING_TTL_SECONDS = 86400


class ConflictError(Exception):
    """目标文件被他人改动 / 批次状态冲突（409）。"""


class ValidationError(Exception):
    """非法路径 / 非法参数（422）。"""


class ApplyError(Exception):
    """写入失败（500，已补偿回滚）。"""


def admin_agent_enabled() -> bool:
    return ENABLE_ADMIN_AGENT


# ── 基础工具 ──

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return _sha256_bytes(f.read())


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    # newline="" 禁用平台换行符转换：Windows 下文本模式会把 \n 改成 \r\n，
    # 导致写入后的二进制哈希与基于 \n 计算的 base_hash/new_hash 不符，
    # 进而使 apply 的 base_hash 预检与 rollback 的 new_hash 校验误判冲突。
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    os.replace(tmp, path)


def _resolve_target(rel_path: str) -> str:
    """路径白名单：必须是 context/ 下的 .md，且不得落在 .staging/.backup/.faiss 内。"""
    if not isinstance(rel_path, str) or not rel_path.startswith("context/") or not rel_path.endswith(".md"):
        raise ValidationError("仅允许编辑 context/ 下的 .md 文件")
    abs_path = os.path.realpath(os.path.join(AGENT_CONFIG_DIR, rel_path))
    context_root = os.path.realpath(CONTEXT_DIR)
    if not (abs_path.startswith(context_root + os.sep) or abs_path == context_root):
        raise ValidationError("非法的目标路径")
    normalized = abs_path.replace("\\", "/")
    if "/.staging/" in normalized or "/.backup/" in normalized or "/.faiss/" in normalized:
        raise ValidationError("非法的目标路径")
    return abs_path


def _make_batch_no() -> str:
    return f"b_{time.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"


def _batch_dir(batch_no: str) -> str:
    return os.path.join(STAGING_DIR, batch_no)


def _load_batch(batch_no: str) -> dict:
    path = os.path.join(_batch_dir(batch_no), "batch.json")
    if not os.path.exists(path):
        raise ConflictError("批次不存在或已过期")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_batch(batch_no: str, batch: dict) -> None:
    _write_text(os.path.join(_batch_dir(batch_no), "batch.json"),
                json.dumps(batch, ensure_ascii=False, indent=2))


def _load_items(batch_no: str) -> list[dict]:
    """按 item_index 排序返回 [{item_index, meta, new_path}]。"""
    items_root = os.path.join(_batch_dir(batch_no), "items")
    if not os.path.isdir(items_root):
        return []
    items = []
    for name in os.listdir(items_root):
        if not name.isdigit():
            continue
        item_dir = os.path.join(items_root, name)
        meta_path = os.path.join(item_dir, "meta.json")
        new_path = os.path.join(item_dir, "new.md")
        if not os.path.exists(meta_path) or not os.path.exists(new_path):
            continue
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        items.append({"item_index": int(name), "meta": meta, "new_path": new_path})
    items.sort(key=lambda x: x["item_index"])
    return items


def _current_pending_batch(session_id: str) -> dict | None:
    """取会话当前 pending 批次（DB 与暂存目录双校验）。"""
    with get_db() as conn:
        conn.row_factory = __import__("sqlite3").Row
        row = conn.execute(
            "SELECT batch_no FROM context_change_batch "
            "WHERE session_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    batch_no = row["batch_no"]
    if not os.path.exists(os.path.join(_batch_dir(batch_no), "batch.json")):
        return None
    return _load_batch(batch_no)


def _unified_diff(old: str, new: str, target: str) -> str:
    diff = difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=f"a/{target}", tofile=f"b/{target}",
    )
    text = "".join(diff)
    if len(text) > 4000:
        return text[:4000] + "\n... (diff 已截断)"
    return text


def _schedule_warmup() -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_warmup_once())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _warmup_once() -> None:
    if _prewarm_lock.locked():
        return
    async with _prewarm_lock:
        try:
            from skills.knowledge_retrieval.hybrid_search import prewarm
            ready = await asyncio.to_thread(prewarm)
            print(f"[context] 索引重建完成 ready={ready}", file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"[context] 索引预热失败：{exc}", file=sys.stderr, flush=True)


async def _update_index(paths: list[str]) -> bool:
    """进程内增量更新索引（禁止子进程调用，见 §11.6）。"""
    if not paths:
        return True
    async with _INDEX_LOCK:
        try:
            from skills.context_transformation.vectorizer import update_document
            from skills.knowledge_retrieval.hybrid_search import refresh_searcher
            results = [await asyncio.to_thread(update_document, p) for p in paths]
            refresh_searcher()
            ok = all(results)
            if ok:
                _schedule_warmup()
            return ok
        except Exception as exc:
            print(f"[context] 索引更新失败：{exc}", file=sys.stderr, flush=True)
            return False


# ── context_editor 工具 handler ──

async def handle_context_editor(task: Task, operator: str, session_id: str = "") -> SkillResult:
    """context_editor 统一入口。session_id 由框架透传，不信任模型参数。"""
    args = task.arguments or {}
    action = (args.get("action") or "").strip()

    if action == "list":
        return SkillResult(_tool_list(args.get("path") or "context/"))
    if action == "read":
        return SkillResult(_tool_read(args.get("path") or "", args.get("section"), args.get("offset"), args.get("limit")))
    if action == "list_changes":
        return SkillResult(_tool_list_changes(session_id))
    if action == "stage_write":
        return await _tool_stage_write(args, operator, session_id)
    return SkillResult("未知 action，请使用 list / read / stage_write / list_changes")


def _tool_list(path: str) -> str:
    rel = path if path.startswith("context/") else "context/"
    root = os.path.realpath(os.path.join(AGENT_CONFIG_DIR, rel))
    if not root.startswith(os.path.realpath(CONTEXT_DIR)):
        return "错误：非法路径"
    lines = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".faiss") and not d.startswith(".")]
        for d in dirnames:
            lines.append(f"[dir]  {os.path.relpath(os.path.join(dirpath, d), AGENT_CONFIG_DIR)}")
        for fn in filenames:
            if fn.lower().endswith(".md"):
                full = os.path.join(dirpath, fn)
                lines.append(f"[file] {os.path.relpath(full, AGENT_CONFIG_DIR)} ({os.path.getsize(full)}B)")
    return "context 文件树：\n" + "\n".join(lines[:200]) if lines else "context 下暂无文件"


def _tool_read(path: str, section: str | None, offset: Any, limit: Any) -> str:
    try:
        abs_path = _resolve_target(path)
    except ValidationError as exc:
        return f"错误：{exc}"
    if not os.path.exists(abs_path):
        return f"错误：文件不存在：{path}（新建请用 stage_write）"
    text = _read_text(abs_path)
    if section:
        pattern = re.compile(rf"^(#+)\s*{re.escape(str(section))}\s*$", re.MULTILINE)
        m = pattern.search(text)
        if not m:
            return f"未找到标题「{section}」。文件大纲：\n" + "\n".join(
                l for l in text.splitlines() if l.startswith("#")
            )[:2000]
        start = m.start()
        nxt = re.search(r"^#+\s", text[m.end():], re.MULTILINE)
        end = m.end() + nxt.start() if nxt else len(text)
        return text[start:end][:6000]
    if offset is not None or limit is not None:
        lines = text.splitlines()
        o = max(0, int(offset or 0))
        l = min(1000, int(limit or 200))
        return "\n".join(f"{i+1+o}: {line}" for i, line in enumerate(lines[o:o + l]))
    headings = "\n".join(l for l in text.splitlines() if l.startswith("#"))[:1500]
    return f"文件大纲：\n{headings}\n\n前 2000 字：\n{text[:2000]}"


async def _tool_stage_write(args: dict, operator: str, session_id: str) -> SkillResult:
    path = (args.get("path") or "").strip()
    mode = (args.get("mode") or "").strip()
    content = args.get("content") or ""
    summary = (args.get("summary") or "")[:50]

    if not session_id:
        return SkillResult("错误：缺少 session_id，无法归入会话批次")
    if not path or not mode:
        return SkillResult("错误：stage_write 需要 path 与 mode")
    try:
        abs_target = _resolve_target(path)
    except ValidationError as exc:
        return SkillResult(f"错误：{exc}")

    # 读取当前内容（新建时为空）
    if os.path.exists(abs_target):
        old_text = _read_text(abs_target)
        base_hash = _sha256_file(abs_target)
        op = "update"
    else:
        old_text = ""
        base_hash = None
        op = "create"

    # 按 mode 生成新内容
    try:
        new_text = _apply_mode(old_text, str(content), mode, args.get("after_heading"))
    except ValueError as exc:
        return SkillResult(f"错误：{exc}")

    batch = _current_pending_batch(session_id)
    new_batch = batch is None
    if new_batch:
        batch_no = _make_batch_no()
        batch = {
            "batch_no": batch_no,
            "session_id": session_id,
            "operator": operator,
            "source": "agent",
            "status": "pending",
            "item_count": 0,
            "summary": summary,
            "created_at": time.time(),
            "closed_at": None,
        }
    else:
        batch_no = batch["batch_no"]

    item_dir = os.path.join(_batch_dir(batch_no), "items")
    os.makedirs(item_dir, exist_ok=True)

    # 同 target 覆盖草稿；新增则追加 item
    item_index = None
    for it in _load_items(batch_no):
        if it["meta"].get("target") == path and it["meta"].get("base_hash") == base_hash:
            item_index = it["item_index"]
            break
    if item_index is None:
        item_index = batch["item_count"]
        batch["item_count"] += 1

    cur_item_dir = os.path.join(item_dir, str(item_index))
    os.makedirs(cur_item_dir, exist_ok=True)
    if base_hash and old_text:
        _write_text(os.path.join(cur_item_dir, "old.md"), old_text)
    _write_text(os.path.join(cur_item_dir, "new.md"), new_text)
    meta = {
        "batch_no": batch_no,
        "item_index": item_index,
        "op": op,
        "target": path,
        "mode": mode,
        "base_hash": base_hash,
        "new_hash": _sha256_bytes(new_text.encode("utf-8")),
        "summary": summary,
        "source": "agent",
    }
    _write_text(os.path.join(cur_item_dir, "meta.json"), json.dumps(meta, ensure_ascii=False, indent=2))
    if new_batch:
        _write_text(os.path.join(_batch_dir(batch_no), "old.md"), old_text)

    if new_batch:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO context_change_batch "
                "(batch_no, session_id, operator, status, item_count, summary, source, created_at) "
                "VALUES (?, ?, ?, 'pending', ?, ?, 'agent', ?)",
                (batch_no, session_id, operator, batch["item_count"], summary, time.time()),
            )
            conn.commit()
    else:
        with get_db() as conn:
            conn.execute(
                "UPDATE context_change_batch SET item_count = ?, summary = ? WHERE batch_no = ?",
                (batch["item_count"], summary, batch_no),
            )
            conn.commit()
    _save_batch(batch_no, batch)

    diff = _unified_diff(old_text, new_text, path)
    change_event = {
        "name": "change",
        "data": {
            "batch_no": batch_no,
            "item_index": item_index,
            "item_count": batch["item_count"],
            "op": op,
            "target": path,
            "summary": summary,
            "diff": diff,
        },
    }
    text = (
        f"已生成变更：批次 {batch_no} 的第 {item_index + 1} 项（待确认）\n"
        f"目标：{path}（{mode}）\n摘要：{summary}\n"
        f"变更后字符数：{len(new_text) - len(old_text):+d}\n"
        f"草稿已暂存，未写入知识库。如需调整请继续说明；全部改动无误后，"
        f"请在下方批次确认条点击「确认并入（N 项）」一次性确认整个批次，不要声称已生效。"
    )
    return SkillResult(text, [change_event])


def _apply_mode(old: str, content: str, mode: str, after_heading: str | None) -> str:
    if mode == "replace_file":
        return content
    if mode == "append":
        return old.rstrip() + "\n" + content.lstrip() + "\n"
    if mode in ("insert_after", "replace_section"):
        heading = (after_heading or "").strip()
        if not heading:
            raise ValueError(f"{mode} 需要 after_heading 参数")
        pattern = re.compile(rf"^(#+)\s*{re.escape(heading)}\s*$", re.MULTILINE)
        m = pattern.search(old)
        if not m:
            raise ValueError(f"未找到标题「{heading}」")
        nxt = re.search(r"^#+\s", old[m.end():], re.MULTILINE)
        end = m.end() + nxt.start() if nxt else len(old)
        if mode == "insert_after":
            insert_pos = end
            return old[:insert_pos].rstrip() + "\n" + content.lstrip() + "\n" + old[insert_pos:]
        return old[:m.start()] + content.rstrip() + "\n\n" + old[end:]
    raise ValueError(f"不支持的 mode：{mode}")


def _tool_list_changes(session_id: str) -> str:
    batch = _current_pending_batch(session_id)
    if not batch:
        return "当前会话没有待确认的变更批次"
    lines = []
    for it in _load_items(batch["batch_no"]):
        meta = it["meta"]
        lines.append(f"#{meta['item_index'] + 1} {meta['target']} - {meta.get('summary','')}")
    return f"待确认批次 {batch['batch_no']}（共 {batch['item_count']} 项）：\n" + "\n".join(lines)


# ── 批次 apply / rollback（原子） ──

def _commit_batch_logs(
    batch_no: str, operator: str, action: str,
    resolved: list[tuple], backups: list[tuple],
    *, source: str, status: str, applied_at: float | None = None,
) -> None:
    now = time.time()
    with get_db() as conn:
        for (item, abs_target, current_hash), (_item2, backup_rel) in zip(resolved, backups):
            meta = item["meta"]
            conn.execute(
                "INSERT INTO context_audit_log "
                "(batch_id, item_index, operator, action, source, target, base_hash, new_hash, backup_path, created_at) "
                "VALUES ((SELECT id FROM context_change_batch WHERE batch_no = ?), ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (batch_no, meta["item_index"], operator, action, source, meta["target"],
                 meta.get("base_hash"), meta.get("new_hash"), backup_rel, now),
            )
        if status == "applied":
            conn.execute(
                "UPDATE context_change_batch SET status='applied', applied_at=? WHERE batch_no=?",
                (applied_at or now, batch_no),
            )
        conn.commit()


def _compensate(written: list[tuple], backups: list[tuple]) -> None:
    backup_map = {id(item): rel for item, rel in backups}
    for item, abs_target in reversed(written):
        rel = backup_map.get(id(item), "")
        if rel:
            backup_file = os.path.join(AGENT_CONFIG_DIR, rel)
            if os.path.exists(backup_file):
                shutil.copy2(backup_file, abs_target)
        else:
            try:
                os.remove(abs_target)
            except OSError:
                pass


async def apply_batch(batch_no: str, operator: str) -> dict:
    """批次级原子确认。锁范围：预检 → 备份 → 写入 → 索引 → 日志（见 §11.6 v1.6）。"""
    async with _BATCH_LOCK:
        batch = _load_batch(batch_no)
        if batch["status"] != "pending":
            raise ConflictError("该批次已处理，请勿重复确认")
        items = _load_items(batch_no)

        # 阶段 1：全量预检
        resolved = []
        for item in items:
            meta = item["meta"]
            abs_target = _resolve_target(meta["target"])
            current_hash = _sha256_file(abs_target)
            if current_hash != meta.get("base_hash"):
                raise ConflictError(
                    f"目标文件已被修改：{meta['target']}，请基于最新版本重新生成该批次"
                )
            resolved.append((item, abs_target, current_hash))

        # 阶段 2：全量备份
        backups = []
        for item, abs_target, current_hash in resolved:
            backup_rel = ""
            if current_hash:
                rel = os.path.relpath(abs_target, CONTEXT_DIR)
                backup_rel = os.path.join(".backup", batch_no, str(item["meta"]["item_index"]), rel).replace("\\", "/")
                backup_file = os.path.join(CONTEXT_DIR, backup_rel)
                os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                shutil.copy2(abs_target, backup_file)
            backups.append((item, backup_rel))

        # 阶段 3：全量写入
        written = []
        try:
            for item, abs_target, _ in resolved:
                new_text = _read_text(item["new_path"])
                _write_text(abs_target, new_text)
                written.append((item, abs_target))
        except Exception:
            _compensate(written, backups)
            raise ApplyError("批次写入失败，已回滚已写入的文件")

        # 阶段 4：进程内索引
        ok = await _update_index([p for _, p in written])

        # 阶段 5：日志 + 状态（单事务）
        _commit_batch_logs(
            batch_no, operator, "apply", resolved, backups,
            source=batch.get("source", "agent"), status="applied", applied_at=time.time(),
        )
        batch["status"] = "applied"
        _save_batch(batch_no, batch)

        # 清理暂存 items（备份保留在 .backup 供回滚）
        shutil.rmtree(os.path.join(_batch_dir(batch_no), "items"), ignore_errors=True)

        return {"batch_no": batch_no, "item_count": len(items), "index_updated": ok}


async def rollback_batch(batch_id: int, operator: str) -> dict:
    """按批次原子回滚。与 apply 共用 _BATCH_LOCK（见 §13.5.3）。"""
    async with _BATCH_LOCK:
        with get_db() as conn:
            conn.row_factory = __import__("sqlite3").Row
            batch = conn.execute(
                "SELECT * FROM context_change_batch WHERE id = ?", (batch_id,)
            ).fetchone()
            if not batch:
                raise ConflictError("批次不存在")
            if batch["status"] not in ("applied", "rolled_back"):
                raise ConflictError("该批次不可回滚")
            items = conn.execute(
                "SELECT * FROM context_audit_log WHERE batch_id = ? AND action = 'apply' ORDER BY item_index",
                (batch_id,),
            ).fetchall()
        if not items:
            raise ConflictError("批次无可回滚的明细")

        # 全量预检：当前文件必须仍是 apply 后的内容
        targets = []
        for row in items:
            abs_target = _resolve_target(row["target"])
            if _sha256_file(abs_target) != row["new_hash"]:
                raise ConflictError(f"文件已被修改：{row['target']}，请刷新后重试")
            targets.append((row, abs_target))

        # 全量还原（失败则按当前快照补偿）
        snapshots = [(row, abs_target, _read_text(abs_target) if os.path.exists(abs_target) else None)
                     for row, abs_target in targets]
        restored = []
        try:
            for row, abs_target in targets:
                backup_rel = row["backup_path"]
                if not backup_rel or row["base_hash"] is None:
                    # 新建文件回滚 → 删除
                    if os.path.exists(abs_target):
                        os.remove(abs_target)
                else:
                    backup_file = os.path.join(CONTEXT_DIR, backup_rel)
                    if not os.path.exists(backup_file):
                        raise ApplyError("备份内容缺失，无法回滚")
                    shutil.copy2(backup_file, abs_target)
                restored.append(abs_target)
        except Exception:
            for row, abs_target, snap in reversed(snapshots):
                if snap is not None:
                    _write_text(abs_target, snap)
                elif os.path.exists(abs_target):
                    os.remove(abs_target)
            raise ApplyError("回滚失败，已还原到回滚前状态")

        ok = await _update_index(restored)

        # 新批次记录（rolled_back）
        new_no = _make_batch_no()
        now = time.time()
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO context_change_batch "
                "(batch_no, session_id, operator, status, item_count, summary, source, restored_from, created_at, applied_at, closed_at) "
                "VALUES (?, ?, ?, 'rolled_back', ?, ?, 'rollback', ?, ?, ?, ?)",
                (new_no, batch["session_id"], operator, len(items),
                 f"回滚批次 {batch['batch_no']}", batch_id, now, now, now),
            )
            new_id = cur.lastrowid
            for row in items:
                conn.execute(
                    "INSERT INTO context_audit_log "
                    "(batch_id, item_index, operator, action, source, target, base_hash, new_hash, backup_path, created_at) "
                    "VALUES (?, ?, ?, 'rollback', 'rollback', ?, ?, ?, ?, ?)",
                    (new_id, row["item_index"], operator, row["target"], row["new_hash"],
                     row["base_hash"], row["backup_path"], now),
                )
            conn.commit()
        return {"batch_no": new_no, "item_count": len(items), "index_updated": ok}


def discard_batch(batch_no: str) -> None:
    """取消 pending 批次：删除暂存目录，DB 标记 discarded，不触碰正式文件。"""
    with get_db() as conn:
        conn.row_factory = __import__("sqlite3").Row
        row = conn.execute(
            "SELECT status FROM context_change_batch WHERE batch_no = ?", (batch_no,)
        ).fetchone()
        if not row:
            raise ConflictError("批次不存在")
        if row["status"] != "pending":
            raise ConflictError("批次已处理")
        conn.execute(
            "UPDATE context_change_batch SET status='discarded', closed_at=? WHERE batch_no=?",
            (time.time(), batch_no),
        )
        conn.commit()
    shutil.rmtree(_batch_dir(batch_no), ignore_errors=True)


def list_batches(
    session_id: str | None = None,
    statuses: list[str] | None = None,
    limit: int = 50,
) -> list[dict]:
    """列出批次及文件明细。statuses 为多状态列表（如 applied/rolled_back）。"""
    clauses = []
    params: list[Any] = []
    if session_id:
        clauses.append("b.session_id = ?")
        params.append(session_id)
    if statuses:
        placeholders = ",".join("?" for _ in statuses)
        clauses.append(f"b.status IN ({placeholders})")
        params.extend(statuses)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with get_db() as conn:
        conn.row_factory = __import__("sqlite3").Row
        rows = conn.execute(
            f"SELECT b.*, s.title AS session_title FROM context_change_batch b "
            f"LEFT JOIN sessions s ON s.id = b.session_id {where} "
            f"ORDER BY b.id DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        result = []
        for row in rows:
            items = conn.execute(
                "SELECT target, action, new_hash, backup_path, item_index FROM context_audit_log "
                "WHERE batch_id = ? ORDER BY item_index", (row["id"],)
            ).fetchall()
            batch_dict = dict(row)
            batch_dict["items"] = [
                {**dict(i), "summary": ""} for i in items
            ]
            result.append(batch_dict)
    return result


async def cleanup_expired_staging() -> int:
    """清理超时的 pending 批次（启动时 + 每小时调用）。"""
    cutoff = time.time() - STAGING_TTL_SECONDS
    with get_db() as conn:
        rows = conn.execute(
            "SELECT batch_no FROM context_change_batch WHERE status='pending' AND created_at < ?",
            (cutoff,),
        ).fetchall()
    cleaned = 0
    for (batch_no,) in rows:
        shutil.rmtree(_batch_dir(batch_no), ignore_errors=True)
        with get_db() as conn:
            conn.execute(
                "UPDATE context_change_batch SET status='discarded', closed_at=? WHERE batch_no=?",
                (time.time(), batch_no),
            )
            conn.commit()
        cleaned += 1
    return cleaned
