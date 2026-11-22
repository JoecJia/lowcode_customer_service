r"""一次性下载 embedding 模型到本地 HuggingFace 缓存。

背景
----
向量检索使用 BAAI/bge-small-zh-v1.5，但 vectorizer.EmbeddingModel 以
SentenceTransformer(model_name, local_files_only=True) 加载。若本地缓存缺失，
加载会抛异常并被 HybridSearcher 静默吞掉（_embedder = None），
导致「混合检索」退化为纯 BM25，且 ready 仍返回 True，问题难以察觉。

本脚本联网把模型拉到本地缓存；之后运行时就无需联网，local_files_only 也能命中。

用法
----
    venv\Scripts\python.exe debug\download_embedding_model.py
    # 如直连 huggingface.co 缓慢，脚本已默认走 hf-mirror 镜像

下载完成后请重启后端，使其在预热阶段加载成功。
"""

from __future__ import annotations

import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
EXPECTED_DIM = 512


def main() -> int:
    # 允许联网：清除离线开关，避免 sentence_transformers 直接走本地缓存
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        os.environ.pop(key, None)
    # 国内直连 huggingface.co 常超时，默认走镜像
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

    print(f"镜像源     : {os.environ['HF_ENDPOINT']}")
    print(f"目标模型   : {MODEL_NAME}")
    print("开始下载（首次约 100MB，请耐心等待）...")

    started = time.perf_counter()
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        print(f"[x] 无法导入 sentence_transformers：{exc}", file=sys.stderr)
        return 2

    try:
        model = SentenceTransformer(MODEL_NAME)
    except Exception as exc:
        print(f"[x] 模型下载失败：{exc}", file=sys.stderr)
        print(
            "    可尝试手动设置镜像后重试：\n"
            "    $env:HF_ENDPOINT='https://hf-mirror.com'",
            file=sys.stderr,
        )
        return 1

    elapsed = time.perf_counter() - started
    dim = model.get_sentence_embedding_dimension()
    cache_root = os.environ.get("HF_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache", "huggingface"
    )

    print(f"\n[√] 下载完成，耗时 {elapsed:.1f}s")
    print(f"    向量维度   : {dim}")
    print(f"    缓存目录   : {cache_root}")
    if dim != EXPECTED_DIM:
        print(
            f"    [!] 维度与 FAISS 索引期望的 {EXPECTED_DIM} 不一致，"
            "索引可能来自其他模型，请核对。",
            file=sys.stderr,
        )

    # 关键校验：确认离线加载同样可以命中缓存（生产代码走的是这条路）
    try:
        SentenceTransformer(MODEL_NAME, local_files_only=True)
        print("    [√] 离线加载校验通过（local_files_only=True 可命中缓存）")
    except Exception as exc:
        print(f"    [x] 离线加载仍失败：{exc}", file=sys.stderr)
        return 1

    print("\n请重启后端，使预热阶段能加载该模型。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
