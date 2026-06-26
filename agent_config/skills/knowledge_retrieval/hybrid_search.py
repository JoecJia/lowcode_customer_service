import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from skills.context_transformation.vectorizer import (
    REPO_DIR,
    EmbeddingModel,
    FAISSIndexManager,
    load_chunk_meta,
)

BM25_K1 = 1.5
BM25_B = 0.75

RRF_K = 60
VECTOR_TOP_K = 10
BM25_TOP_K = 10


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
        # 仅在 FAISS 索引存在时才加载嵌入模型，避免无索引时卡在模型下载
        if self._loaded and self._meta and self._meta.get("chunks"):
            self._embedder = embedder or EmbeddingModel()
        else:
            self._embedder = None

    @property
    def ready(self) -> bool:
        return self._loaded

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


class HybridSearcher:
    def __init__(self, embedder: Optional[EmbeddingModel] = None):
        self._bm25 = BM25Retriever()
        self._vector = VectorRetriever(embedder=embedder)

    @property
    def ready(self) -> bool:
        return self._vector.ready

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not query.strip():
            return []

        bm25_results = self._bm25.search(query, top_k=BM25_TOP_K)
        vector_results = self._vector.search(query, top_k=VECTOR_TOP_K)

        fused_ids = rrf_fusion(bm25_results, vector_results, k=RRF_K, final_top_k=top_k)

        meta = load_chunk_meta()
        all_chunks = meta.get("chunks", [])
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
