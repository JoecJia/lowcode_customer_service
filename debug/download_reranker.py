"""把精排模型（bge-reranker-base）下载到 HuggingFace 缓存目录，供离线加载使用。

背景
----
服务器无外网，`CrossEncoder(..., local_files_only=True)` 需要模型已在本地缓存。
本脚本按 HF 缓存目录结构直接落盘（snapshots/<sha>/<file>），写入 refs/main，
与 huggingface_hub 的目录布局一致，因此运行时按模型名即可命中。

为何不用 snapshot_download：hf-mirror 的 HEAD 响应缺少 hub 校验所需的元信息头，
会抛 FileMetadataError；改为直连下载 + 断点续传。

用法
----
    python debug/download_reranker.py
    python debug/download_reranker.py --check      # 只检查本地是否已就绪
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request

REPO_ID = "BAAI/bge-reranker-base"
REVISION = "2cfc18c9415c912f9d8155881c133215df768a70"
FILES = (
    "config.json",
    "model.safetensors",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
)
ENDPOINT = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")


def cache_root() -> str:
    base = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    return os.path.join(base, "hub")


def repo_dir() -> str:
    return os.path.join(cache_root(), "models--" + REPO_ID.replace("/", "--"))


def snapshot_dir() -> str:
    return os.path.join(repo_dir(), "snapshots", REVISION)


def remote_url(filename: str) -> str:
    return f"{ENDPOINT}/{REPO_ID}/resolve/{REVISION}/{filename}"


def download_one(filename: str, target: str) -> int:
    os.makedirs(os.path.dirname(target), exist_ok=True)
    have = os.path.getsize(target) if os.path.exists(target) else 0
    req = urllib.request.Request(remote_url(filename), headers={"User-Agent": "curl/8"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except Exception as exc:
        print(f"[x] {filename} 请求失败: {exc}", file=sys.stderr)
        return 1

    total = int(resp.headers.get("Content-Length") or 0) + have
    mode = "ab" if have and resp.status == 206 else "wb"
    if mode == "wb":
        have = 0
    print(f"    {filename}: 从 {have / 1e6:.0f}MB 开始，目标 {total / 1e6:.0f}MB")

    written = have
    last_report = time.time()
    with open(target, mode) as f:
        while True:
            block = resp.read(1024 * 1024)
            if not block:
                break
            f.write(block)
            written += len(block)
            if time.time() - last_report > 5:
                pct = written / total * 100 if total else 0
                print(f"      {written / 1e6:.0f}MB / {total / 1e6:.0f}MB ({pct:.0f}%)")
                last_report = time.time()
    print(f"    {filename}: 完成 {os.path.getsize(target) / 1e6:.1f}MB")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只检查是否已就绪")
    args = parser.parse_args()

    snap = snapshot_dir()
    missing = [f for f in FILES if not os.path.exists(os.path.join(snap, f))]
    print(f"缓存目录: {snap}")
    if args.check:
        print("状态:", "就绪" if not missing else f"缺少 {missing}")
        return 0 if not missing else 1
    if not missing:
        print("[√] 已就绪，无需下载")
        return 0

    print(f"模型: {REPO_ID} @ {REVISION[:8]}")
    print(f"源: {ENDPOINT}（{sum(1 for _ in missing)} 个文件待下载）")
    started = time.perf_counter()
    for filename in missing:
        if download_one(filename, os.path.join(snap, filename)) != 0:
            return 1

    refs = os.path.join(repo_dir(), "refs")
    os.makedirs(refs, exist_ok=True)
    with open(os.path.join(refs, "main"), "w", encoding="utf-8") as f:
        f.write(REVISION)

    print(f"\n[√] 下载完成，耗时 {time.perf_counter() - started:.0f}s")
    print("    下一步: python debug/sweep_rerank.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
