"""RRF 融合参数网格对比（离线实验，不改生产代码）。

只跑一次 BM25 与向量的召回，然后离线用不同「候选深度 / 双路权重 / RRF k」重排，
输出各配置的 Recall / MRR，用于决定 hybrid_search.py 的常量取值。

用法:
    python debug/sweep_fusion.py
    python debug/sweep_fusion.py --top 20
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

CANDIDATES = (10, 20, 30)
WEIGHTS = (
    ("1:1", 1.0, 1.0),
    ("1:1.5", 1.0, 1.5),
    ("1:2", 1.0, 2.0),
    ("1:3", 1.0, 3.0),
    ("1:5", 1.0, 5.0),
    ("1.5:1", 1.5, 1.0),
    ("2:1", 2.0, 1.0),
    ("only_vec", 0.0, 1.0),
    ("only_bm25", 1.0, 0.0),
)
RRF_KS = (60,)
CC_ALPHAS = (0.3, 0.5, 0.6, 0.7, 0.8, 1.0)


def fuse(bm25, vector, k: int, w_bm25: float, w_vec: float, depth: int, top_k: int) -> list[int]:
    scores: dict[int, float] = {}
    for rank, (pos, _score) in enumerate(bm25[:depth]):
        scores[pos] = scores.get(pos, 0.0) + w_bm25 / (k + rank + 1)
    for rank, (pos, _score) in enumerate(vector[:depth]):
        scores[pos] = scores.get(pos, 0.0) + w_vec / (k + rank + 1)
    return sorted(scores, key=lambda p: scores[p], reverse=True)[:top_k]


def _minmax(items: list[tuple[int, float]]) -> dict[int, float]:
    if not items:
        return {}
    values = [s for _, s in items]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    return {pos: (score - lo) / span for pos, score in items}


def fuse_cc(bm25, vector, alpha: float, depth: int, top_k: int) -> list[int]:
    """归一化凸组合：alpha 为向量路权重，BM25 原始分与余弦分先各自 min-max 归一。"""
    scores: dict[int, float] = {}
    for pos, score in _minmax(bm25[:depth]).items():
        scores[pos] = scores.get(pos, 0.0) + (1 - alpha) * score
    for pos, score in _minmax(vector[:depth]).items():
        scores[pos] = scores.get(pos, 0.0) + alpha * score
    return sorted(scores, key=lambda p: scores[p], reverse=True)[:top_k]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depth", type=int, default=30, help="预取深度（不小于候选深度上限）")
    parser.add_argument("--top", type=int, default=15, help="展示前 N 个配置")
    args = parser.parse_args()

    queries = load_queries(os.path.join(REPO_DIR, "agent_config", "skills",
                                        "knowledge_retrieval", "eval_queries.json"))
    searcher = HybridSearcher()
    if not searcher.status().get("vector_ready"):
        print("[x] 向量通道不可用", file=sys.stderr)
        return 1

    chunks = searcher._bm25._chunks
    labeled = [q for q in queries if q["expected_files"]]
    print(f"样本 {len(labeled)} 条，预取深度 {args.depth}")

    cache = []
    for item in labeled:
        bm25 = searcher._bm25.search(item["query"], top_k=args.depth)
        vector = searcher._vector.search(item["query"], top_k=args.depth)
        cache.append((item, bm25, vector))

    def print_table(title: str, rows: list[dict], key_name: str) -> None:
        rows.sort(key=lambda x: (x["r3"], x["r1"], x["mrr"]), reverse=True)
        print(f"\n{title}")
        print(f"{'depth':>5} {key_name:>9} {'R@1':>6} {'R@3':>6} {'R@5':>6} {'KW@3':>6} {'MRR':>6}")
        for row in rows[: args.top]:
            print(f"{row['depth']:>5} {row['label']:>9} "
                  f"{row['r1']:>6.3f} {row['r3']:>6.3f} {row['r5']:>6.3f} "
                  f"{row['kw3']:>6.3f} {row['mrr']:>6.3f}")

    rrf_rows = []
    for depth in CANDIDATES:
        for label, w_bm25, w_vec in WEIGHTS:
            for rrf_k in RRF_KS:
                ranks, kw_ranks = [], []
                for item, bm25, vector in cache:
                    fused = fuse(bm25, vector, rrf_k, w_bm25, w_vec, depth, 10)
                    results = [chunks[p] for p in fused]
                    expected = {normalize_path(p) for p in item["expected_files"]}
                    fr, kr = match_rank(results, expected, item["answer_keywords"])
                    ranks.append(fr)
                    kw_ranks.append(kr)
                n = len(ranks)
                rrf_rows.append({
                    "depth": depth,
                    "label": label,
                    "r1": sum(1 for r in ranks if 0 < r <= 1) / n,
                    "r3": sum(1 for r in ranks if 0 < r <= 3) / n,
                    "r5": sum(1 for r in ranks if 0 < r <= 5) / n,
                    "kw3": sum(1 for r in kw_ranks if 0 < r <= 3) / n,
                    "mrr": sum(1.0 / r for r in ranks if r) / n,
                    "ranks": ranks,
                    "kw_ranks": kw_ranks,
                })
    print_table("=== 加权 RRF（k=60）===", rrf_rows, "w(bm25:vec)")

    cc_rows = []
    for depth in CANDIDATES:
        for alpha in CC_ALPHAS:
            ranks, kw_ranks = [], []
            for item, bm25, vector in cache:
                fused = fuse_cc(bm25, vector, alpha, depth, 10)
                results = [chunks[p] for p in fused]
                expected = {normalize_path(p) for p in item["expected_files"]}
                fr, kr = match_rank(results, expected, item["answer_keywords"])
                ranks.append(fr)
                kw_ranks.append(kr)
            n = len(ranks)
            cc_rows.append({
                "depth": depth,
                "label": f"a={alpha}",
                "r1": sum(1 for r in ranks if 0 < r <= 1) / n,
                "r3": sum(1 for r in ranks if 0 < r <= 3) / n,
                "r5": sum(1 for r in ranks if 0 < r <= 5) / n,
                "kw3": sum(1 for r in kw_ranks if 0 < r <= 3) / n,
                "mrr": sum(1.0 / r for r in ranks if r) / n,
                "ranks": ranks,
                "kw_ranks": kw_ranks,
            })
    print_table("=== 归一化凸组合（alpha=向量权重）===", cc_rows, "alpha")

    current = [r for r in rrf_rows if r["depth"] == 10 and r["label"] == "1:1"]
    if current:
        c = current[0]
        print(f"\n线上现有配置 depth=10 1:1: R@1 {c['r1']:.3f} / R@3 {c['r3']:.3f} / KW@3 {c['kw3']:.3f} / MRR {c['mrr']:.3f}")

    # 配对 bootstrap：46 条样本下单条约 2.2pp，差异是否可信需要显著性检验
    import random

    def hit_rate(ranks: list[int], k: int) -> float:
        return sum(1 for r in ranks if 0 < r <= k) / len(ranks)

    def bootstrap(a: dict, b: dict, k: int, rounds: int = 4000) -> tuple[float, float, float]:
        ra, rb = a["ranks"], b["ranks"]
        m = len(ra)
        diffs = []
        for _ in range(rounds):
            idx = [random.randrange(m) for _ in range(m)]
            diffs.append(hit_rate([ra[i] for i in idx], k) - hit_rate([rb[i] for i in idx], k))
        diffs.sort()
        return (sum(1 for d in diffs if d > 0) / rounds,
                diffs[int(0.025 * rounds)], diffs[int(0.975 * rounds)])

    best_cc = max(cc_rows, key=lambda r: (r["r1"], r["mrr"]))
    if current:
        print(f"\n配对 bootstrap（{best_cc['depth']}/{best_cc['label']} vs 线上 1:1）:")
        for k in (1, 3):
            win, lo, hi = bootstrap(best_cc, current[0], k)
            print(f"  R@{k} 提升概率 {win:.2f}，95%CI [{lo:+.3f}, {hi:+.3f}]")

    target = [r for r in rrf_rows if r["depth"] == 10 and r["label"] == "1:1.5"]
    if current and target:
        b = target[0]
        print("\n配对 bootstrap（10/1:1.5 vs 线上 1:1）——各指标均不下降的候选:")
        for k in (1, 3):
            win, lo, hi = bootstrap(b, current[0], k)
            print(f"  R@{k} 提升概率 {win:.2f}，95%CI [{lo:+.3f}, {hi:+.3f}]")
        print(f"  绝对值: R@1 {b['r1']:.3f} / R@3 {b['r3']:.3f} / KW@3 {b['kw3']:.3f} / MRR {b['mrr']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
