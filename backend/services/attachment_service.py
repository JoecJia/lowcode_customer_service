"""附件校验、落盘与读取服务。

首版附件以 Base64 JSON 入站，后端解码后写入本地文件系统；
数据库 messages.attachments 只保存元数据与 storage.ref，不保存 Base64 原文。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import (
    MAX_ATTACHMENTS_COUNT,
    MAX_ATTACHMENTS_TOTAL_SIZE,
    MAX_IMAGE_SIZE,
    MAX_PDF_SIZE,
    UPLOAD_DIR,
)

_IMAGE_DATA_URL_RE = re.compile(r"^data:image/(png|jpeg|webp);base64,(.+)$", re.DOTALL)
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_PDF_MAGIC = b"%PDF-"

_ALLOWED_MIMES = {
    "image": {"image/png", "image/jpeg", "image/webp"},
    "pdf": {"application/pdf"},
}


class AttachmentError(ValueError):
    """附件校验失败，路由层统一转成 422。"""


@dataclass
class PreparedAttachment:
    """已通过校验、等待落盘的附件。"""

    id: str
    kind: str
    name: str
    mime: str
    size: int
    sha256: str
    data: bytes
    width: int | None = None
    height: int | None = None
    page_count: int | None = None


def _clean_filename(name: str) -> str:
    filename = (name or "").strip()
    if not filename:
        raise AttachmentError("文件名不能为空")
    if len(filename) > 200:
        raise AttachmentError("文件名过长")
    if "/" in filename or "\\" in filename or ".." in filename or "\x00" in filename:
        raise AttachmentError("文件名包含非法字符")
    return filename


def _decode_base64(value: str, field: str) -> bytes:
    if not value or not isinstance(value, str):
        raise AttachmentError(f"{field} 不能为空")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AttachmentError(f"{field} 不是合法的 Base64 编码") from exc


def _decode_payload(payload: dict[str, Any]) -> tuple[bytes, str]:
    """返回 (文件字节, mime)。"""
    kind = payload.get("kind")
    name = payload.get("name")
    mime = payload.get("mime")
    declared_size = payload.get("size", 0)

    if kind not in _ALLOWED_MIMES:
        raise AttachmentError("不支持的附件类型")
    if mime not in _ALLOWED_MIMES[kind]:
        raise AttachmentError("不支持的文件格式")
    _clean_filename(name)

    try:
        declared_size = int(declared_size)
    except (TypeError, ValueError) as exc:
        raise AttachmentError("文件大小无效") from exc
    if declared_size <= 0:
        raise AttachmentError("文件大小无效")

    limit = MAX_PDF_SIZE if kind == "pdf" else MAX_IMAGE_SIZE
    if declared_size > limit:
        raise AttachmentError("PDF 不能超过 20MB" if kind == "pdf" else "图片不能超过 10MB")

    if kind == "image":
        data_url = payload.get("data_url") or ""
        matched = _IMAGE_DATA_URL_RE.match(data_url)
        if not matched:
            raise AttachmentError("图片必须使用 data URL 传入")
        data = _decode_base64(matched.group(2), "data_url")
    else:
        data = _decode_base64(payload.get("base64") or "", "base64")

    # 客户端声明大小与实际字节数偏差过大时拒绝，避免伪造 size 绕过限制
    if abs(len(data) - declared_size) > 1024:
        raise AttachmentError("文件大小与实际内容不匹配")

    if kind == "pdf":
        if not data.startswith(_PDF_MAGIC):
            raise AttachmentError("PDF 文件无效")
    elif mime == "image/png":
        if not data.startswith(_PNG_MAGIC):
            raise AttachmentError("PNG 文件无效")
    elif mime == "image/jpeg":
        if not data.startswith(_JPEG_MAGIC):
            raise AttachmentError("JPEG 文件无效")
    elif mime == "image/webp":
        if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
            raise AttachmentError("WebP 文件无效")

    return data, mime


def prepare_attachments(payloads: list[dict[str, Any]]) -> list[PreparedAttachment]:
    """校验并准备附件；任何一项失败都会抛 AttachmentError。"""
    if len(payloads) > MAX_ATTACHMENTS_COUNT:
        raise AttachmentError(f"最多上传 {MAX_ATTACHMENTS_COUNT} 个附件")

    total_size = 0
    pdf_count = 0
    prepared: list[PreparedAttachment] = []

    for payload in payloads:
        data, mime = _decode_payload(payload)
        total_size += int(payload.get("size", 0))
        if payload.get("kind") == "pdf":
            pdf_count += 1

        prepared.append(
            PreparedAttachment(
                id=f"att_{uuid.uuid4().hex[:8]}",
                kind=payload["kind"],
                name=_clean_filename(payload["name"]),
                mime=mime,
                size=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                data=data,
            )
        )

    if pdf_count > 1:
        raise AttachmentError("每次最多上传 1 个 PDF")
    if total_size > MAX_ATTACHMENTS_TOTAL_SIZE:
        raise AttachmentError("附件总大小不能超过 20MB")

    return prepared


def _extension(mime: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
    }.get(mime, ".bin")


def persist_attachment(session_id: str, message_id: int, item: PreparedAttachment) -> dict[str, Any]:
    """把附件字节写入本地文件，返回可落库的元数据。"""
    rel = Path("sessions") / str(session_id) / "messages" / str(message_id) / f"{item.id}{_extension(item.mime)}"
    target = Path(UPLOAD_DIR) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(item.data)

    metadata: dict[str, Any] = {
        "id": item.id,
        "kind": item.kind,
        "name": item.name,
        "mime": item.mime,
        "size": item.size,
        "sha256": item.sha256,
        "created_at": int(time.time()),
        "storage": {"type": "local", "ref": rel.as_posix()},
    }
    if item.kind == "image":
        if item.width is not None:
            metadata["width"] = item.width
        if item.height is not None:
            metadata["height"] = item.height
    elif item.kind == "pdf":
        metadata["page_count"] = item.page_count
    return metadata


def resolve_attachment_path(ref: str) -> Path:
    """把 storage.ref 解析为 UPLOAD_DIR 下的安全绝对路径。"""
    if not ref or not isinstance(ref, str):
        raise AttachmentError("附件路径无效")
    parts = Path(ref).parts
    if Path(ref).is_absolute() or ".." in parts or parts[0] != "sessions":
        raise AttachmentError("附件路径无效")

    root = Path(UPLOAD_DIR).resolve()
    target = (root / ref).resolve()
    try:
        if os.path.commonpath([str(root), str(target)]) != str(root):
            raise AttachmentError("附件路径越界")
    except ValueError as exc:
        raise AttachmentError("附件路径越界") from exc
    return target


def read_attachment_bytes(metadata: dict[str, Any]) -> bytes:
    """按元数据读取附件原始字节。"""
    storage = metadata.get("storage") or {}
    if storage.get("type") != "local":
        raise AttachmentError("暂不支持该附件存储类型")
    path = resolve_attachment_path(storage.get("ref") or "")
    if not path.is_file():
        raise AttachmentError("附件文件不存在")
    return path.read_bytes()


def attachment_exists(metadata: dict[str, Any]) -> bool:
    storage = metadata.get("storage") or {}
    if storage.get("type") != "local":
        return False
    try:
        return resolve_attachment_path(storage.get("ref") or "").is_file()
    except AttachmentError:
        return False
