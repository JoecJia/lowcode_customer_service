def knowledge_retrieval(_repo_dir: str, query: str, top_k: int = 3) -> dict:
    from skills.knowledge_retrieval.hybrid_search import retrieve

    return retrieve(query, top_k=top_k)


def format_knowledge_retrieval_result(result: dict) -> str:
    hit_text = (result.get("hit_text") or "").strip()
    images = result.get("images") or []
    out = []
    out.append("### 命中文本")
    out.append(hit_text if hit_text else "（未命中）")
    if images:
        out.append("")
        out.append("### 命中图片（可选）")
        for img in images:
            alt = (img.get("alt") or "").strip()
            path = (img.get("path") or "").strip()
            source = (img.get("source") or "").strip()
            out.append(f"- alt: {alt}")
            out.append(f"  path: {path}")
            out.append(f"  source: {source}")
    return "\n".join(out).strip()
