"""精排（cross-encoder）离线验证：对融合候选重新打分，测量收益与 CPU 延迟。

用法:
    python debug/sweep_rerank.py
    python debug/sweep_rerank.py --depths 10,20,30
"""
from __future__ import annotations

import argparse
import os
import sys
import time

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_DIR, "agent_config"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from skills.knowledge_retrieval.evaluate import load_queries, match_rank, normalize_path
from skills.knowledge_retrieval.hybrid_search import HybridSearcher

RERANK_MODEL = "BAAI/bge-reranker-base"
CAP = 2
TOP_K = 3
KS = (1, 3)


def rrf(bm25, vector, k: int = 60, depth: int = 10, limit: int = 30) -> list[int]:
    scores: dict[int, float] = {}
    for rank, (pos, _s) in enumerate(bm25[:depth]):
        scores[pos] = scores.get(pos, 0.0) + 1.0 / (k + rank + 1)
    for rank, (pos, _s) in enumerate(vector[:depth]):
        scores[pos] = scores.get(pos, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda p: scores[p], reverse=True)[:limit]


def cap_select(order: list[int], chunks: list[dict], top_k: int, cap: int = CAP) -> list[int]:
    picked, per_source = [], {}
    for pos in order:
        source = normalize_path(chunks[pos]["source_file"])
        if per_source.get(source, 0) >= cap:
            continue
        picked.append(pos)
        per_source[source] = per_source.get(source, 0) + 1
        if len(picked) >= top_k:
            break
    for pos in order:
        if len(picked) >= top_k:
            break
        if pos not in picked:
            picked.append(pos)
    return picked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depths", default="10,20", help="精排候选数量")
    parser.add_argument("--max-chars", type=int, default=300, help="送入精排的正文截断长度")
    parser.add_argument("--queries", default=os.path.join(REPO_DIR, "agent_config", "skills",
                                                          "knowledge_retrieval", "eval_queries.json"))
    args = parser.parse_args()

    depths = [int(x) for x in args.depths.split(",") if x.strip()]
    queries = [q for q in load_queries(args.queries) if q["expected_files"]]
    searcher = HybridSearcher()
    chunks = searcher._bm25._chunks

    print(f"样本 {len(queries)} 条，加载精排模型 {RERANK_MODEL} ...")
    started = time.perf_counter()
    from sentence_transformers import CrossEncoder
    reranker = CrossEncoder(RERANK_MODEL, max_length=512, local_files_only=True, device="cpu")
    print(f"模型加载 {time.perf_counter() - started:.1f}s")

    # 先生成候选（与线上一致的融合，不做多样性约束），并缓存
    cache = []
    for item in queries:
        bm25 = searcher._bm25.search(item["query"], top_k=10)
        vector = searcher._vector.search(item["query"], top_k=10)
        expected = {normalize_path(p) for p in item["expected_files"]}
        cache.append((item, rrf(bm25, vector), expected))

    stats = {}

    def record(name: str, ranks: list[int], kw_ranks: list[int], latencies: list[float]) -> None:
        n = len(ranks)
        stats[name] = {
            "ranks": ranks,
            "kw_ranks": kw_ranks,
            **{f"r{k}": sum(1 for r in ranks if 0 < r <= k) / n for k in KS},
            "kw3": sum(1 for r in kw_ranks if 0 < r <= 3) / n,
            "mrr": sum(1.0 / r for r in ranks if r) / n,
            "p50": sorted(latencies)[len(latencies) // 2] if latencies else 0.0,
            "p95": sorted(latencies)[int(len(latencies) * 0.95) - 1] if latencies else 0.0,
        }

    # 基线：融合 + 多样性约束，不精排
    ranks, kw_ranks = [], []
    for item, cand, expected in cache:
        results = [chunks[p] for p in cap_select(cand, chunks, TOP_K)]
        fr, kr = match_rank(results, expected, item["answer_keywords"])
        ranks.append(fr)
        kw_ranks.append(kr)
    record("不精排(RRF+cap2)", ranks, kw_ranks, [0.0] * len(ranks))

    for depth in depths:
        ranks, kw_ranks, latencies = [], [], []
        for item, cand, expected in cache:
            top = cand[:depth]
            pairs = [[item["query"], chunks[p]["content"][: args.max_chars]] for p in top]
            t0 = time.perf_counter()
            scores = reranker.predict(pairs)
            latencies.append((time.perf_counter() - t0) * 1000)

            order = [p for p, _ in sorted(zip(top, scores), key=lambda x: x[1], reverse=True)]
            results = [chunks[p] for p in cap_select(order, chunks, TOP_K)]
            fr, kr = match_rank(results, expected, item["answer_keywords"])
            ranks.append(fr)
            kw_ranks.append(kr)
        record(f"精排 top{depth}", ranks, kw_ranks, latencies)

    print(f"\n样本 {len(queries)} 条，返回 top-{TOP_K}")
    print(f"{'策略':<18} {'R@1':>6} {'R@3':>6} {'KW@3':>6} {'MRR':>6} {'p50ms':>7} {'p95ms':>7}")
    for name, m in stats.items():
        print(f"{name:<18} {m['r1']:>6.3f} {m['r3']:>6.3f} {m['kw3']:>6.3f} "
              f"{m['mrr']:>6.3f} {m['p50']:>7.0f} {m['p95']:>7.0f}")

    import random

    def bootstrap(a: list[int], b: list[int], k: int, rounds: int = 4000):
        m = len(a)
        diffs = []
        for _ in range(rounds):
            idx = [random.randrange(m) for _ in range(m)]
            ra = sum(1 for i in idx if 0 < a[i] <= k) / m
            rb = sum(1 for i in idx if 0 < b[i] <= k) / m
            diffs.append(ra - rb)
        diffs.sort()
        return (sum(1 for d in diffs if d > 0) / rounds,
                diffs[int(0.025 * rounds)], diffs[int(0.975 * rounds)])

    base = stats["不精排(RRF+cap2)"]["ranks"]
    print("\n配对 bootstrap（对比不精排）:")
    for name, m in stats.items():
        if name.startswith("不精排"):
            continue
        w1, l1, h1 = bootstrap(m["ranks"], base, 1)
        w3, l3, h3 = bootstrap(m["ranks"], base, 3)
        print(f"  {name:<14} R@1 {w1:.2f} CI[{l1:+.3f},{h1:+.3f}]  R@3 {w3:.2f} CI[{l3:+.3f},{h3:+.3f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
