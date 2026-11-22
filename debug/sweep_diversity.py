"""文件级多样性约束实验：融合后限制单个来源文件占据的 top-k 名额。

动机：form_usage_guide.md 占索引 48% 的 chunk，实测 top-3 有 32% 被同一文件占满，
         70% 的名额被单文件拿走，导致答案位于其他文件时被挤掉。

用法:
    python debug/sweep_diversity.py
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
from skills.knowledge_retrieval.hybrid_search import HybridSearcher, rrf_fusion

RRF_K = 60
CAPS = (0, 1, 2, 3)  # 0 = 不限（现状）
KS = (1, 3, 5)


def select(candidates: list[int], chunks: list[dict], cap: int, top_k: int) -> list[int]:
    """按融合顺序贪心选取，限制单文件最多 cap 个（cap=0 表示不限）。"""
    if cap <= 0:
        return candidates[:top_k]
    picked: list[int] = []
    per_file: dict[str, int] = {}
    for pos in candidates:
        source = normalize_path(chunks[pos]["source_file"])
        if per_file.get(source, 0) >= cap:
            continue
        picked.append(pos)
        per_file[source] = per_file.get(source, 0) + 1
        if len(picked) >= top_k:
            break
    # 名额没填满时用剩余候选补齐，避免因约束导致召回截断
    for pos in candidates:
        if len(picked) >= top_k:
            break
        if pos not in picked:
            picked.append(pos)
    return picked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", default=os.path.join(REPO_DIR, "agent_config", "skills",
                                                          "knowledge_retrieval", "eval_queries.json"))
    parser.add_argument("--top", type=int, default=3, help="最终返回条数（生产默认 3）")
    args = parser.parse_args()

    queries = [q for q in load_queries(args.queries) if q["expected_files"]]
    searcher = HybridSearcher()
    chunks = searcher._bm25._chunks

    cache = []
    for item in queries:
        bm25 = searcher._bm25.search(item["query"], top_k=10)
        vector = searcher._vector.search(item["query"], top_k=10)
        fused = rrf_fusion(bm25, vector, k=RRF_K, final_top_k=20)
        expected = {normalize_path(p) for p in item["expected_files"]}
        cache.append((item, fused, expected))

    stats = {}
    for cap in CAPS:
        ranks, kw_ranks = [], []
        for item, fused, expected in cache:
            picked = select(fused, chunks, cap, max(KS))
            results = [chunks[p] for p in picked]
            fr, kr = match_rank(results, expected, item["answer_keywords"])
            ranks.append(fr)
            kw_ranks.append(kr)
        n = len(ranks)
        stats[cap] = {
            "ranks": ranks,
            "kw_ranks": kw_ranks,
            **{f"r{k}": sum(1 for r in ranks if 0 < r <= k) / n for k in KS},
            "kw3": sum(1 for r in kw_ranks if 0 < r <= 3) / n,
            "mrr": sum(1.0 / r for r in ranks if r) / n,
        }

    print(f"\n样本 {len(queries)} 条，最终返回 top-{args.top}")
    print(f"{'cap':>4} {'R@1':>6} {'R@3':>6} {'R@5':>6} {'KW@3':>6} {'MRR':>6}")
    for cap in CAPS:
        m = stats[cap]
        label = "不限" if cap == 0 else str(cap)
        print(f"{label:>4} {m['r1']:>6.3f} {m['r3']:>6.3f} {m['r5']:>6.3f} {m['kw3']:>6.3f} {m['mrr']:>6.3f}")

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

    base = stats[0]["ranks"]
    print("\n配对 bootstrap（对比 cap=不限）:")
    for cap in CAPS:
        if cap == 0:
            continue
        w1, l1, h1 = bootstrap(stats[cap]["ranks"], base, 1)
        w3, l3, h3 = bootstrap(stats[cap]["ranks"], base, 3)
        print(f"  cap={cap}: R@1 提升概率 {w1:.2f} CI[{l1:+.3f},{h1:+.3f}]  "
              f"R@3 提升概率 {w3:.2f} CI[{l3:+.3f},{h3:+.3f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
