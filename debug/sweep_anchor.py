"""向量锚点实验：把纯向量排名第一的结果固定为首位，其余名额由融合结果填充。

动机：混合检索 R@1 一直低于纯向量（0.686 vs 0.716），RRF 等权会把向量给出的
最优首条压到第 2、3 位；而生产链路 top_k=3，LLM 按顺序读取，首条权重最高。

用法:
    python debug/sweep_anchor.py
"""
from __future__ import annotations

import argparse
import os
import sys

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_DIR, "agent_config"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from skills.knowledge_retrieval.evaluate import load_queries, match_rank, normalize_path
from skills.knowledge_retrieval.hybrid_search import HybridSearcher

RRF_K = 60
TOP_K = 3
CAP = 2
KS = (1, 3, 5)


def rrf(bm25, vector, w_bm25: float = 1.0, w_vec: float = 1.0, depth: int = 10) -> list[int]:
    scores: dict[int, float] = {}
    for rank, (pos, _s) in enumerate(bm25[:depth]):
        scores[pos] = scores.get(pos, 0.0) + w_bm25 / (RRF_K + rank + 1)
    for rank, (pos, _s) in enumerate(vector[:depth]):
        scores[pos] = scores.get(pos, 0.0) + w_vec / (RRF_K + rank + 1)
    return sorted(scores, key=lambda p: scores[p], reverse=True)


def convex(bm25, vector, alpha: float = 0.6, depth: int = 10) -> list[int]:
    def norm(items):
        if not items:
            return {}
        vals = [s for _, s in items]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        return {p: (s - lo) / span for p, s in items[:depth]}

    scores: dict[int, float] = {}
    for pos, s in norm(bm25).items():
        scores[pos] = scores.get(pos, 0.0) + (1 - alpha) * s
    for pos, s in norm(vector).items():
        scores[pos] = scores.get(pos, 0.0) + alpha * s
    return sorted(scores, key=lambda p: scores[p], reverse=True)


def cap_select(order: list[int], chunks: list[dict], cap: int, top_k: int) -> list[int]:
    if cap <= 0:
        return order[:top_k]
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


def anchor_first(order: list[int], vector: list[tuple[int, float]], min_score: float = -1.0) -> list[int]:
    if not vector:
        return order
    top_pos, top_score = vector[0]
    if top_score < min_score:
        return order
    return [top_pos] + [p for p in order if p != top_pos]


def anchor_if_agree(
    order: list[int],
    vector: list[tuple[int, float]],
    bm25: list[tuple[int, float]],
    bm25_depth: int,
) -> list[int]:
    """仅当向量首条也出现在 BM25 前 N 名时才锚定——用双路一致性代替失效的余弦阈值。"""
    if not vector:
        return order
    top_pos = vector[0][0]
    if any(pos == top_pos for pos, _ in bm25[:bm25_depth]):
        return [top_pos] + [p for p in order if p != top_pos]
    return order


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", default=os.path.join(REPO_DIR, "agent_config", "skills",
                                                          "knowledge_retrieval", "eval_queries.json"))
    args = parser.parse_args()

    queries = [q for q in load_queries(args.queries) if q["expected_files"]]
    searcher = HybridSearcher()
    chunks = searcher._bm25._chunks

    cache = []
    for item in queries:
        bm25 = searcher._bm25.search(item["query"], top_k=10)
        vector = searcher._vector.search(item["query"], top_k=10)
        expected = {normalize_path(p) for p in item["expected_files"]}
        cache.append((item, bm25, vector, expected))

    def build(order_fn, cap=CAP, top_k=TOP_K, pool=9):
        def run(item, bm25, vector):
            order = order_fn(bm25, vector)[:pool]
            return cap_select(order, chunks, cap, top_k)
        return run

    rrf11 = lambda b, v: rrf(b, v, 1.0, 1.0)  # noqa: E731
    strategies = {
        "现状(prod) pool9": build(rrf11),
        "现状 pool20": build(rrf11, pool=20),
        "RRF1:1.5 pool20": build(lambda b, v: rrf(b, v, 1.0, 1.5), pool=20),
        "凸组合0.6 pool20": build(lambda b, v: convex(b, v, 0.6), pool=20),
        "锚点 cap1": build(lambda b, v: anchor_first(rrf11(b, v), v), cap=1, pool=20),
        "锚点 cos>=0.55": build(lambda b, v: anchor_first(rrf11(b, v), v, 0.55), pool=20),
        "锚点 cos>=0.60": build(lambda b, v: anchor_first(rrf11(b, v), v, 0.60), pool=20),
        "锚点 需bm25top3": build(lambda b, v: anchor_if_agree(rrf11(b, v), v, b, 3), pool=20),
        "锚点 需bm25top5": build(lambda b, v: anchor_if_agree(rrf11(b, v), v, b, 5), pool=20),
        "锚点 需bm25top10": build(lambda b, v: anchor_if_agree(rrf11(b, v), v, b, 10), pool=20),
        "纯向量 pool20": build(lambda b, v: [p for p, _ in v], pool=20),
    }

    stats = {}
    for name, fn in strategies.items():
        ranks, kw_ranks = [], []
        for item, bm25, vector, expected in cache:
            picked = fn(item, bm25, vector)
            results = [chunks[p] for p in picked if 0 <= p < len(chunks)]
            fr, kr = match_rank(results, expected, item["answer_keywords"])
            ranks.append(fr)
            kw_ranks.append(kr)
        n = len(ranks)
        stats[name] = {
            "ranks": ranks,
            "kw_ranks": kw_ranks,
            **{f"r{k}": sum(1 for r in ranks if 0 < r <= k) / n for k in KS},
            "kw3": sum(1 for r in kw_ranks if 0 < r <= 3) / n,
            "mrr": sum(1.0 / r for r in ranks if r) / n,
        }

    print(f"\n样本 {len(queries)} 条，返回 top-{TOP_K}（R@5 在只返回 3 条时无意义，不列）")
    print(f"{'策略':<18} {'R@1':>6} {'R@3':>6} {'KW@3':>6} {'MRR':>6}")
    for name, m in stats.items():
        print(f"{name:<18} {m['r1']:>6.3f} {m['r3']:>6.3f} {m['kw3']:>6.3f} {m['mrr']:>6.3f}")

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

    base = stats["现状 RRF1:1 cap2"]["ranks"]
    print("\n配对 bootstrap（对比现状）:")
    for name, m in stats.items():
        if name.startswith("现状"):
            continue
        w1, l1, h1 = bootstrap(m["ranks"], base, 1)
        w3, l3, h3 = bootstrap(m["ranks"], base, 3)
        print(f"  {name:<20} R@1 {w1:.2f} CI[{l1:+.3f},{h1:+.3f}]  R@3 {w3:.2f} CI[{l3:+.3f},{h3:+.3f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
