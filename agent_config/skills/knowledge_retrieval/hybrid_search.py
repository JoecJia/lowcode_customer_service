import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from skills.context_transformation.vectorizer import (
    REPO_DIR,
    EmbeddingModel,
    FAISSIndexManager,
    check_index_compatibility,
    load_chunk_meta,
)
from skills.knowledge_retrieval.reranker import Reranker

BM25_K1 = 1.5
BM25_B = 0.75

RRF_K = 60
VECTOR_TOP_K = 10
BM25_TOP_K = 10
# 文件级多样性约束：单个来源文件在最终结果中最多占几条。
# form_usage_guide.md 占索引约 48% 的 chunk，实测 top-3 有 32% 被同一文件占满，
# 答案位于其他文件时会被挤掉；限制为 2 条后评测 R@3 从 0.873 提升到 0.902。
# 设为 0 可关闭该约束。
MAX_CHUNKS_PER_SOURCE = 2
# 精排开关与候选数：实测 top-10 精排使 R@1 0.686->0.765、KW@3 0.814->0.853，
# 代价约 0.45s/请求（CPU）。模型缺失时自动降级为不精排。
RERANK_ENABLED = True
RERANK_TOP_N = 10


def _tokenize(text: str) -> list[str]:
    import jieba
    return list(jieba.cut(text))


class BM25Retriever:
    def __init__(self):
        from rank_bm25 import BM25Okapi
        meta = load_chunk_meta()
        chunks = meta.get("chunks", [])
        self._chunks = chunks
        self._corpus = [c["content"] for c in chunks]
        self._tokenized = [_tokenize(doc) for doc in self._corpus]
        self._bm25 = BM25Okapi(self._tokenized, k1=BM25_K1, b=BM25_B) if self._tokenized else None

    @property
    def ready(self) -> bool:
        return self._bm25 is not None and bool(self._chunks)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def search(self, query: str, top_k: int = BM25_TOP_K) -> list[tuple[int, float]]:
        if self._bm25 is None:
            return []
        tokenized = _tokenize(query)
        scores = self._bm25.get_scores(tokenized)
        if not len(scores):
            return []
        top_k = min(top_k, len(scores))
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [(idx, float(scores[idx])) for idx in top_indices]


class VectorRetriever:
    def __init__(self, embedder: Optional[EmbeddingModel] = None):
        self._index_mgr = FAISSIndexManager()
        self._loaded = self._index_mgr.load()
        self._meta = load_chunk_meta() if self._loaded else None
        self._vector_error = ""
        # 仅在 FAISS 索引存在时才加载嵌入模型，避免无索引时卡在模型下载
        if self._loaded and self._meta and self._meta.get("chunks"):
            try:
                self._embedder = embedder or EmbeddingModel()
            except Exception:
                import traceback
                traceback.print_exc()
                self._embedder = None
                self._vector_error = "embedding 模型加载失败（本地缓存缺失？）"
        else:
            self._embedder = None

        # 索引与模型不同源时禁用向量通道：否则检索不报错但排序不可信
        if self._embedder is not None:
            ok, reason = check_index_compatibility(self._meta, self._embedder, self._index_mgr.dim)
            if not ok:
                print(f"[hybrid_search] 向量通道已禁用：{reason}", file=sys.stderr)
                self._embedder = None
                self._vector_error = reason

    @property
    def ready(self) -> bool:
        # 保持既有语义：索引加载成功即视为可用（向量通道失效时仍可退回 BM25）
        return self._loaded

    @property
    def vector_ready(self) -> bool:
        """向量通道是否真正可用：索引与 embedding 模型都已就绪。

        注意 vector_ready=False 时 search() 会静默返回空，混合检索实际只跑 BM25。
        这种情况通常意味着 embedding 模型不在本地缓存，用 /ready 可以提前发现。
        """
        return self._loaded and self._embedder is not None

    @property
    def vector_error(self) -> str:
        """向量通道不可用的具体原因（空字符串表示正常）。"""
        return self._vector_error

    def search(self, query: str, top_k: int = VECTOR_TOP_K) -> list[tuple[int, float]]:
        if not self._loaded or self._meta is None or self._embedder is None:
            return []
        query_vec = self._embedder.encode([query], is_query=True)
        distances, indices = self._index_mgr.search(query_vec, top_k)
        results = []
        for dist, idx in zip(distances, indices):
            if idx < 0 or idx >= len(self._meta["chunks"]):
                continue
            results.append((int(idx), float(dist)))
        return results


def rrf_fusion(
    bm25_results: list[tuple[int, float]],
    vector_results: list[tuple[int, float]],
    k: int = RRF_K,
    final_top_k: int = 5,
) -> list[int]:
    scores: dict[int, float] = {}
    for rank, (chunk_id, _) in enumerate(bm25_results):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1.0 / (k + rank + 1)

    for rank, (chunk_id, _) in enumerate(vector_results):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1.0 / (k + rank + 1)

    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
    return sorted_ids[:final_top_k]


def diversify_by_source(
    fused_ids: list[int],
    chunks: list[dict],
    top_k: int,
    max_per_source: int = MAX_CHUNKS_PER_SOURCE,
) -> list[int]:
    """按融合顺序做文件级配额筛选，避免单个大文件占满名额。

    max_per_source <= 0 时退化为直接截断。配额用完仍不足 top_k 时，
    用剩余候选补齐，保证召回数量不因约束而减少。
    """
    if max_per_source <= 0:
        return fused_ids[:top_k]

    picked: list[int] = []
    per_source: dict[str, int] = {}
    for cid in fused_ids:
        if cid < 0 or cid >= len(chunks):
            continue
        source = chunks[cid].get("source_file", "")
        if per_source.get(source, 0) >= max_per_source:
            continue
        picked.append(cid)
        per_source[source] = per_source.get(source, 0) + 1
        if len(picked) >= top_k:
            return picked

    for cid in fused_ids:
        if len(picked) >= top_k:
            break
        if cid not in picked and 0 <= cid < len(chunks):
            picked.append(cid)
    return picked


class HybridSearcher:
    def __init__(self, embedder: Optional[EmbeddingModel] = None):
        self._bm25 = BM25Retriever()
        self._vector = VectorRetriever(embedder=embedder)
        self._reranker = Reranker()

    @property
    def ready(self) -> bool:
        return self._vector.ready

    def status(self) -> dict:
        """检索链路状态，供 /ready 就绪检查使用。"""
        result = {
            "bm25_ready": self._bm25.ready,
            "vector_ready": self._vector.vector_ready,
            "chunks": self._bm25.chunk_count,
        }
        if self._vector.vector_error:
            result["vector_error"] = self._vector.vector_error
        if RERANK_ENABLED:
            result["rerank_ready"] = self._reranker.loaded
            if self._reranker.error:
                result["rerank_error"] = self._reranker.error
        return result

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not query.strip():
            return []

        bm25_results = self._bm25.search(query, top_k=BM25_TOP_K)
        vector_results = self._vector.search(query, top_k=VECTOR_TOP_K)

        meta = load_chunk_meta()
        all_chunks = meta.get("chunks", [])

        # 多取一些候选：先满足精排所需候选数，再供多样性约束挑选
        candidate_k = max(top_k, RERANK_TOP_N if RERANK_ENABLED else top_k * 3)
        candidate_k = min(candidate_k, len(all_chunks))
        fused_ids = rrf_fusion(bm25_results, vector_results, k=RRF_K, final_top_k=candidate_k)

        if RERANK_ENABLED and fused_ids:
            passages = [
                all_chunks[i].get("content", "") if 0 <= i < len(all_chunks) else ""
                for i in fused_ids
            ]
            order = self._reranker.reorder(query, passages)
            if order is not None:
                fused_ids = [fused_ids[i] for i in order]

        fused_ids = diversify_by_source(fused_ids, all_chunks, top_k)

        results = []
        for cid in fused_ids:
            if cid < 0 or cid >= len(all_chunks):
                continue
            chunk = dict(all_chunks[cid])
            chunk["score"] = None
            results.append(chunk)
        return results


_searcher: Optional[HybridSearcher] = None


def _get_searcher() -> HybridSearcher:
    global _searcher
    if _searcher is None:
        _searcher = HybridSearcher()
    return _searcher


def refresh_searcher() -> None:
    global _searcher
    _searcher = None


def prewarm() -> bool:
    """预热检索链路：构建检索器单例，并空跑一次检索。

    构造过程加载 BM25 语料、FAISS 索引与 embedding 模型（实测约 11 秒）；
    空跑一次是为了触发 PyTorch 首次前向与 FAISS 首次寻址——否则这段冷成本
    会落在首个用户请求上（实测约 2 秒）。
    """
    searcher = _get_searcher()
    if searcher.ready:
        try:
            searcher.search("预热检索", top_k=1)
        except Exception:
            import traceback

            traceback.print_exc()
    # 精排模型首次加载约 1.5~6s；提前加载，避免落在首个用户请求上。
    # 模型缺失时 load() 只失败一次并降级，不影响检索可用性。
    if RERANK_ENABLED:
        searcher._reranker.load()
    return searcher.ready


def status() -> dict:
    """返回检索链路状态；未初始化时不会触发构建（避免就绪检查反而拉高延迟）。"""
    if _searcher is None:
        return {
            "initialized": False,
            "bm25_ready": False,
            "vector_ready": False,
            "chunks": 0,
        }
    return {"initialized": True, **_searcher.status()}


def retrieve(query: str, top_k: int = 3) -> dict:
    if not query.strip():
        return {"hit_text": "", "images": []}

    searcher = _get_searcher()
    if not searcher.ready:
        return {"hit_text": "", "images": []}

    results = searcher.search(query, top_k=top_k)

    hit_sections: list[str] = []
    images: list[dict] = []
    for r in results:
        source_file = r.get("source_file", "")
        header_chain = r.get("header_chain", "")
        content = r.get("content", "")
        prefix = f"[{header_chain}]" if header_chain else f"[source] {source_file}"
        hit_sections.append(f"{prefix}\n{source_file}\n{content}")

        for img in r.get("images", []):
            img_entry = {
                "alt": img.get("alt", ""),
                "path": img.get("path", ""),
                "source": source_file,
            }
            images.append(img_entry)

    hit_text = "\n\n---\n\n".join(hit_sections).strip()
    return {"hit_text": hit_text, "images": images}
