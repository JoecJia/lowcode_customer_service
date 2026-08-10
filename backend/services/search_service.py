def knowledge_retrieval(_repo_dir: str, query: str, top_k: int = 3) -> dict:
    from skills.knowledge_retrieval.hybrid_search import retrieve

    return retrieve(query, top_k=top_k)


def _normalize_image_path(path: str) -> str:
    """将 markdown 中的相对路径（如 ../assets/xxx/image.png）转为服务端绝对路径（/assets/xxx/image.png）。"""
    import re
    # ../assets/ → /assets/
    path = re.sub(r'(?:\.\./)+assets/', '/assets/', path)
    return path


def format_knowledge_retrieval_result(result: dict) -> str:
    hit_text = (result.get("hit_text") or "").strip()
    images = result.get("images") or []
    out = []
    out.append("### 命中文本")
    out.append(hit_text if hit_text else "（未命中）")
    if images:
        out.append("")
        out.append("### 命中图片（可选）")
        out.append("使用 ![图片说明](图片路径) 的 markdown 格式展示图片，例如：")
        for img in images:
            alt = (img.get("alt") or "").strip()
            path = _normalize_image_path((img.get("path") or "").strip())
            source = (img.get("source") or "").strip()
            # 直接给出 markdown 图片语法，LLM 可直接复制使用
            out.append(f"- ![{alt}]({path})")
            out.append(f"  source: {source}")
    return "\n".join(out).strip()
