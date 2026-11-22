"""语义检索评测基线（Recall / MRR / 命中率），供检索链路调优前后对比使用。

用途
----
1. 量化当前检索质量：文件级命中 Recall@k、内容级命中率、MRR；
2. 横向对比三条通道：hybrid / bm25 / vector，为调参（候选数、RRF 权重、分块）提供依据；
3. 输出 JSON 基线，后续改动可 `--compare` 做回归对比，防止越改越差。

评测集会随知识库演进失效：增删文档后请同步维护 `eval_queries.json`，
并用 `--validate` 检查标注是否指向仍存在的文件与关键词。

用法
----
    # 先校验评测集标注本身是否正确
    python agent_config/skills/knowledge_retrieval/evaluate.py --validate

    # 跑三条通道，输出 Recall/MRR（默认 k=1,3,5）
    python agent_config/skills/knowledge_retrieval/evaluate.py

    # 保存基线 / 与基线对比
    python agent_config/skills/knowledge_retrieval/evaluate.py --json debug/eval_baseline.json
    python agent_config/skills/knowledge_retrieval/evaluate.py --compare debug/eval_baseline.json

    # 只看某一类问题
    python agent_config/skills/knowledge_retrieval/evaluate.py --category faq --verbose
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT_CONFIG_DIR = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, AGENT_CONFIG_DIR)

# Windows 控制台默认 GBK，命中片段可能含 emoji，统一按 UTF-8 输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_QUERIES = os.path.join(HERE, "eval_queries.json")
MODES = ("hybrid", "bm25", "vector")
# 生产链路 knowledge_retrieval 默认 top_k=3，分类统计按该口径汇报
CATEGORY_K = 3


def normalize_path(path: str) -> str:
    return (path or "").replace("\\", "/").strip()


def load_queries(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    queries = data.get("queries", data) if isinstance(data, dict) else data
    for i, item in enumerate(queries):
        item.setdefault("id", f"q{i + 1:02d}")
        item.setdefault("category", "uncategorized")
        item.setdefault("expected_files", [])
        item.setdefault("answer_keywords", [])
        item["query"] = (item.get("query") or "").strip()
    return [q for q in queries if q["query"]]


def run_query(searcher, mode: str, query: str, top_k: int) -> tuple[list[dict], float]:
    """返回 [(chunk, score)] 与耗时(ms)。chunk 的 source_file 保持元数据原样。"""
    started = time.perf_counter()
    if mode == "hybrid":
        results = searcher.search(query, top_k=top_k)
    elif mode == "bm25":
        chunks = searcher._bm25._chunks  # 元数据顺序，与 BM25 打分的下标一致
        results = []
        for pos, _score in searcher._bm25.search(query, top_k=top_k):
            if 0 <= pos < len(chunks):
                results.append(dict(chunks[pos]))
    elif mode == "vector":
        chunks = searcher._bm25._chunks
        results = []
        for pos, score in searcher._vector.search(query, top_k=top_k):
            if 0 <= pos < len(chunks):
                chunk = dict(chunks[pos])
                chunk["score"] = score
                results.append(chunk)
    else:
        raise ValueError(f"unknown mode: {mode}")
    elapsed = (time.perf_counter() - started) * 1000
    return results, elapsed


def match_rank(results: list[dict], expected_files: set[str], keywords: list[str]) -> tuple[int, int]:
    """返回 (首个命中期望文件的名次, 首个包含答案关键词的名次)，1-based，未命中为 0。"""
    file_rank = 0
    keyword_rank = 0
    for rank, chunk in enumerate(results, start=1):
        src = normalize_path(chunk.get("source_file", ""))
        if not file_rank and src in expected_files:
            file_rank = rank
        if not keyword_rank and keywords:
            content = chunk.get("content", "")
            if any(kw and kw in content for kw in keywords):
                keyword_rank = rank
    return file_rank, keyword_rank


def evaluate(searcher, queries: list[dict], mode: str, ks: list[int], verbose: bool) -> dict:
    """每个 k 都按 k 实际召回后评测，等价于线上以 top_k=k 调用时的真实表现。

    注意：不能"取大 K 再截断"——融合的候选池大小会随 top_k 变化，
    截断口径会与线上不一致（实测会差 1~2 条样本）。
    """
    per_query = []
    latencies = {k: [] for k in ks}

    for item in queries:
        expected = {normalize_path(p) for p in item["expected_files"]}
        entry = {
            "id": item["id"],
            "category": item["category"],
            "query": item["query"],
            "labeled": bool(item["expected_files"]),
            "by_k": {},
        }
        for k in ks:
            results, elapsed = run_query(searcher, mode, item["query"], k)
            latencies[k].append(elapsed)
            file_rank, keyword_rank = match_rank(results, expected, item["answer_keywords"])
            entry["by_k"][k] = {
                "file_rank": file_rank,
                "keyword_rank": keyword_rank,
                "top_files": [normalize_path(r.get("source_file", "")) for r in results[:3]],
            }
        per_query.append(entry)

    labeled = [q for q in per_query if q["labeled"]]
    n_labeled = max(len(labeled), 1)
    metrics = {"n_queries": len(per_query), "n_labeled": len(labeled), "mode": mode, "by_k": {}}
    for k in ks:
        file_hits = sum(1 for q in labeled if 0 < q["by_k"][k]["file_rank"] <= k)
        keyword_hits = sum(1 for q in labeled if 0 < q["by_k"][k]["keyword_rank"] <= k)
        mrr_file = sum((1.0 / q["by_k"][k]["file_rank"]) for q in labeled if q["by_k"][k]["file_rank"]) / n_labeled
        mrr_keyword = sum(
            (1.0 / q["by_k"][k]["keyword_rank"]) for q in labeled if q["by_k"][k]["keyword_rank"]
        ) / n_labeled
        metrics["by_k"][k] = {
            "file_recall": file_hits / n_labeled,
            "keyword_recall": keyword_hits / n_labeled,
            "mrr_file": mrr_file,
            "mrr_keyword": mrr_keyword,
        }

    latency_k = max(ks)
    metrics["latency_ms"] = {
        "p50": round(percentile(latencies[latency_k], 50), 1),
        "p95": round(percentile(latencies[latency_k], 95), 1),
        "mean": round(sum(latencies[latency_k]) / max(len(latencies[latency_k]), 1), 1),
        "at_k": latency_k,
    }
    metrics["per_query"] = per_query
    metrics["by_category"] = category_summary(labeled, category_k=CATEGORY_K if CATEGORY_K in ks else max(ks))

    if verbose:
        print_misses(per_query, max(ks))
    return metrics


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(pct / 100 * (len(ordered) - 1)))))
    return ordered[idx]


def category_summary(labeled: list[dict], category_k: int) -> dict:
    k = category_k
    buckets: dict[str, list[dict]] = {}
    for q in labeled:
        buckets.setdefault(q["category"], []).append(q)
    out = {}
    for name, items in buckets.items():
        hit = sum(1 for q in items if 0 < q["by_k"][k]["file_rank"] <= k)
        out[name] = {"n": len(items), f"file_recall@{k}": round(hit / len(items), 3)}
    return out


def print_misses(per_query: list[dict], max_k: int) -> None:
    misses = [
        q for q in per_query
        if q["labeled"] and (q["by_k"][max_k]["file_rank"] == 0 or q["by_k"][max_k]["file_rank"] > max_k)
    ]
    if not misses:
        print("  无未命中样本")
        return
    print(f"  未命中样本（共 {len(misses)} 条，期望文件未进入 top-{max_k}）：")
    for q in misses:
        print(f"    - [{q['id']}] {q['query']}")
        print(f"      实际 top3: {q['by_k'][max_k]['top_files']}")


def validate(queries: list[dict], searcher) -> int:
    """校验标注：文件是否存在、关键词是否真的出现在该文件中。"""
    chunks_by_file: dict[str, list[str]] = {}
    for chunk in searcher._bm25._chunks:
        chunks_by_file.setdefault(normalize_path(chunk["source_file"]), []).append(chunk["content"])

    problems = 0
    for item in queries:
        if not item["expected_files"]:
            print(f"[跳过] {item['id']} 无期望文件标注")
            continue
        if not item["answer_keywords"]:
            print(f"[缺少关键词] {item['id']}")
            problems += 1
            continue

        present = []
        for raw in item["expected_files"]:
            path = normalize_path(raw)
            if path not in chunks_by_file:
                print(f"[缺失文件] {item['id']} -> {path}")
                problems += 1
                continue
            present.append(path)
        if not present:
            continue

        # 多文件标注时，关键词分散在不同候选文件里也算合法：只要任一文件包含即可
        joined = "\n".join("\n".join(chunks_by_file[path]) for path in present)
        missing = [kw for kw in item["answer_keywords"] if kw not in joined]
        if missing:
            print(f"[关键词不在文件内] {item['id']} -> {present} 缺失: {missing}")
            problems += 1
    print(f"校验完成：{len(queries)} 条标注，问题 {problems} 处")
    return problems


def print_report(all_metrics: dict[int, dict], ks: list[int]) -> dict:
    summary = {}
    for mode, metrics in all_metrics.items():
        print(f"\n=== 通道: {mode} | 样本 {metrics['n_labeled']} 条 | "
              f"耗时 p50 {metrics['latency_ms']['p50']}ms / p95 {metrics['latency_ms']['p95']}ms ===")
        header = f"{'k':>3} {'文件Recall':>10} {'内容命中':>10} {'MRR(文件)':>10} {'MRR(内容)':>10}"
        print(header)
        for k in ks:
            m = metrics["by_k"][k]
            print(f"{k:>3} {m['file_recall']:>10.3f} {m['keyword_recall']:>10.3f} "
                  f"{m['mrr_file']:>10.3f} {m['mrr_keyword']:>10.3f}")
        if metrics["by_category"]:
            print("  分类：" + "，".join(
                f"{name} {data[f'file_recall@{CATEGORY_K}']:.2f}(n={data['n']})"
                for name, data in sorted(metrics["by_category"].items())
            ))
        summary[mode] = {
            "file_recall": {k: round(metrics["by_k"][k]["file_recall"], 4) for k in ks},
            "keyword_recall": {k: round(metrics["by_k"][k]["keyword_recall"], 4) for k in ks},
            "mrr_file": {k: round(metrics["by_k"][k]["mrr_file"], 4) for k in ks},
            "mrr_keyword": {k: round(metrics["by_k"][k]["mrr_keyword"], 4) for k in ks},
        }
    return summary


def compare_with_baseline(path: str, current: dict, mode: str, k: int) -> None:
    with open(path, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    base = baseline.get("metrics", {}).get(mode, {}).get("file_recall", {}).get(str(k))
    now = current.get(mode, {}).get("file_recall", {}).get(k)
    if base is None or now is None:
        print(f"[compare] 基线缺少 mode={mode} k={k} 的 file_recall，跳过")
        return
    delta = now - base
    flag = "提升" if delta > 0 else ("下降" if delta < 0 else "持平")
    print(f"[compare] mode={mode} k={k} 文件Recall: {base:.3f} -> {now:.3f} ({flag} {delta:+.3f})")


def main() -> int:
    parser = argparse.ArgumentParser(description="语义检索评测基线")
    parser.add_argument("--queries", default=DEFAULT_QUERIES, help="评测集 JSON 路径")
    parser.add_argument("--k", default="1,3,5", help="评测截断位，逗号分隔")
    parser.add_argument("--mode", default="all", choices=("all",) + MODES)
    parser.add_argument("--category", default=None, help="只跑指定分类")
    parser.add_argument("--validate", action="store_true", help="仅校验评测集标注")
    parser.add_argument("--json", default=None, help="保存本次结果为 JSON 基线")
    parser.add_argument("--compare", default=None, help="与基线 JSON 对比 file_recall")
    parser.add_argument("--verbose", action="store_true", help="打印未命中样本")
    args = parser.parse_args()

    ks = sorted({int(x) for x in args.k.split(",") if x.strip()})
    queries = load_queries(args.queries)
    if args.category:
        queries = [q for q in queries if q["category"] == args.category]
    if not queries:
        print("没有可评测的样本", file=sys.stderr)
        return 2

    from skills.knowledge_retrieval.hybrid_search import HybridSearcher

    started = time.perf_counter()
    searcher = HybridSearcher()
    load_ms = (time.perf_counter() - started) * 1000
    print(f"检索链路加载完成（{load_ms:.0f}ms）: {searcher.status()}")
    if not searcher.ready:
        print("[x] 检索链路不可用，请先运行 diagnose.py", file=sys.stderr)
        return 1

    if args.validate:
        return 0 if validate(queries, searcher) == 0 else 1

    modes = MODES if args.mode == "all" else (args.mode,)
    all_metrics = {}
    for mode in modes:
        all_metrics[mode] = evaluate(searcher, queries, mode, ks, args.verbose)
    summary = print_report(all_metrics, ks)

    if args.compare:
        for mode in modes:
            for k in ks:
                compare_with_baseline(args.compare, summary, mode, k)

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        payload = {
            "meta": {
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "queries_file": os.path.relpath(args.queries),
                "retrieval_status": searcher.status(),
                "n_queries": len(queries),
            },
            "metrics": summary,
            "details": {mode: all_metrics[mode]["per_query"] for mode in modes},
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n基线已保存: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
