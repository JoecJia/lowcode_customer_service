"""多模态消息 content 构造与上下文计权。

图片使用 Ark Chat API 的 image_url part；PDF 使用 file part。
无附件时继续返回字符串，保证纯文本链路与旧会话完全兼容。
"""

from __future__ import annotations

import base64
from typing import Any

from config import ARK_IMAGE_DETAIL
from services.attachment_service import AttachmentError, read_attachment_bytes

IMAGE_TOKEN_COST = 1280
PDF_TOKEN_COST_FALLBACK = 2048


def _encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def build_user_content(text: str, attachments: list[dict[str, Any]] | None) -> str | list[dict[str, Any]]:
    """把用户文本与附件元数据构造成 Ark messages[].content。

    - 图片：data URL + detail
    - PDF：data:application/pdf;base64,... + filename（方舟 Chat API 实测格式）
    - 多图/多附件在前，文字在后；无文字时不追加 text part
    """
    if not attachments:
        return text

    parts: list[dict[str, Any]] = []
    for meta in attachments:
        try:
            data = read_attachment_bytes(meta)
        except AttachmentError:
            # 附件文件缺失时不阻塞对话；历史消息仍保留卡片与错误提示
            continue

        encoded = _encode(data)
        if meta.get("kind") == "image":
            parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{meta.get('mime', 'image/png')};base64,{encoded}",
                    "detail": ARK_IMAGE_DETAIL,
                },
            })
        elif meta.get("kind") == "pdf":
            parts.append({
                "type": "file",
                "file": {
                    "file_data": f"data:application/pdf;base64,{encoded}",
                    "filename": meta.get("name") or "document.pdf",
                },
            })

    if text:
        parts.append({"type": "text", "text": text})

    return parts if parts else text


def content_weight(content: Any) -> int:
    """估算 content 的上下文权重，兼容字符串与多模态数组。"""
    if isinstance(content, str):
        return len(content)
    if not isinstance(content, list):
        return 0

    weight = 0
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text":
            weight += len(part.get("text") or "")
        elif part_type == "image_url":
            weight += IMAGE_TOKEN_COST
        elif part_type == "file":
            file_meta = part.get("file") or {}
            # PDF 官方按视觉分页处理；有页数时按页数估算，否则使用保守值
            page_count = file_meta.get("page_count")
            if isinstance(page_count, int) and page_count > 0:
                weight += IMAGE_TOKEN_COST * page_count
            else:
                weight += PDF_TOKEN_COST_FALLBACK
    return weight


def has_multimodal_part(messages: list[dict[str, Any]]) -> bool:
    """判断上下文中是否包含图片/PDF part，用于选择视觉模型。"""
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") in {"image_url", "file"}:
                    return True
    return False
