"""分块参数网格实验：不同 CHUNK_MAX_CHARS 下重建索引并评测检索质量。

注意：本脚本会改写生产索引（context/.faiss/），跑完后会按默认值重建恢复。
建议在无请求的本地环境运行。

用法:
    python debug/sweep_chunking.py --chars 350,500,700
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

from skills.context_transformation import vectorizer as V
from skills.knowledge_retrieval.evaluate import load_queries, match_rank, normalize_path

DEFAULT_CHARS = 500
KS = (1, 3, 5)


def rebuild(chars: int, embedder) -> dict:
    V.CHUNK_MAX_CHARS = chars
    md_files = V.iter_md_files(V.REPO_DIR)
    started = time.perf_counter()
    mgr, meta = V.build_index_from_docs(md_files, embedder=embedder)
    mgr.save()
    V.save_chunk_meta(meta)
    elapsed = time.perf_counter() - started

    from skills.knowledge_retrieval import hybrid_search as H
    H.refresh_searcher()
    lengths = [len(c["content"]) for c in meta["chunks"]]
    return {
        "chars": chars,
        "chunks": len(meta["chunks"]),
        "avg_len": round(sum(lengths) / max(len(lengths), 1), 1),
        "build_s": round(elapsed, 1),
        "searcher": H.HybridSearcher(),
    }


def evaluate(searcher, queries: list[dict], fetch_k: int = 10) -> dict:
    from skills.knowledge_retrieval.evaluate import run_query

    ranks, kw_ranks = [], []
    for item in queries:
        results, _ = run_query(searcher, "hybrid", item["query"], fetch_k)
        expected = {normalize_path(p) for p in item["expected_files"]}
        fr, kr = match_rank(results, expected, item["answer_keywords"])
        ranks.append(fr)
        kw_ranks.append(kr)

    n = len(ranks)
    out = {"ranks": ranks, "kw_ranks": kw_ranks, "n": n}
    for k in KS:
        out[f"r{k}"] = sum(1 for r in ranks if 0 < r <= k) / n
    out["kw3"] = sum(1 for r in kw_ranks if 0 < r <= 3) / n
    out["mrr"] = sum(1.0 / r for r in ranks if r) / n
    return out


def bootstrap(a: list[int], b: list[int], k: int, rounds: int = 4000) -> tuple[float, float, float]:
    import random

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chars", default="350,500,700", help="测试的 CHUNK_MAX_CHARS 取值")
    parser.add_argument("--queries", default=os.path.join(REPO_DIR, "agent_config", "skills",
                                                          "knowledge_retrieval", "eval_queries.json"))
    args = parser.parse_args()

    configs = [int(x) for x in args.chars.split(",") if x.strip()]
    queries = [q for q in load_queries(args.queries) if q["expected_files"]]
    print(f"样本 {len(queries)} 条，测试分块上限: {configs}")

    embedder = V.EmbeddingModel()
    results = {}
    try:
        for chars in configs:
            print(f"\n[M] 重建索引 CHUNK_MAX_CHARS={chars} ...")
            info = rebuild(chars, embedder)
            print(f"    chunks={info['chunks']} avg_len={info['avg_len']} 重建耗时={info['build_s']}s")
            metrics = evaluate(info["searcher"], queries)
            metrics.update({key: info[key] for key in ("chars", "chunks", "avg_len", "build_s")})
            results[chars] = metrics
    finally:
        print(f"\n[M] 恢复默认索引 CHUNK_MAX_CHARS={DEFAULT_CHARS} ...")
        restore = rebuild(DEFAULT_CHARS, embedder)
        print(f"    已恢复: chunks={restore['chunks']} avg_len={restore['avg_len']}")

    print(f"\n{'chars':>6} {'chunks':>7} {'avg_len':>8} {'R@1':>6} {'R@3':>6} {'R@5':>6} {'KW@3':>6} {'MRR':>6}")
    for chars in configs:
        m = results[chars]
        print(f"{chars:>6} {m['chunks']:>7} {m['avg_len']:>8.1f} "
              f"{m['r1']:>6.3f} {m['r3']:>6.3f} {m['r5']:>6.3f} {m['kw3']:>6.3f} {m['mrr']:>6.3f}")

    base = results.get(DEFAULT_CHARS)
    if base:
        print(f"\n配对 bootstrap（对比 {DEFAULT_CHARS}）:")
        for chars in configs:
            if chars == DEFAULT_CHARS:
                continue
            win1, lo1, hi1 = bootstrap(results[chars]["ranks"], base["ranks"], 1)
            win3, lo3, hi3 = bootstrap(results[chars]["ranks"], base["ranks"], 3)
            print(f"  {chars}: R@1 提升概率 {win1:.2f} CI[{lo1:+.3f},{hi1:+.3f}]  "
                  f"R@3 提升概率 {win3:.2f} CI[{lo3:+.3f},{hi3:+.3f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
