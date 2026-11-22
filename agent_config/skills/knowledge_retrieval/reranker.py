"""精排（cross-encoder）封装：对混合检索的候选做 query-passage 逐对打分。

为什么需要
----------
混合检索只能"重排已有候选"：BM25 与向量的分数尺度不同、语义置信度不可比
（实测余弦分对错例完全重叠），所以首条正确率上不去（R@1 0.686）。
cross-encoder 直接对 (query, passage) 建模，实测 R@1 提升到 0.765、
KW@3 从 0.814 提升到 0.853。

部署要求
--------
服务器无外网，模型必须已在本地 HF 缓存（否则 `local_files_only` 加载失败）。
缺失时本模块静默降级：检索照常返回融合结果，只是不精排。
准备缓存见 `debug/download_reranker.py`。
"""
from __future__ import annotations

import os
import sys
import traceback
from typing import Optional

RERANK_MODEL_NAME = "BAAI/bge-reranker-base"
# 送入精排的正文截断长度：chunk 开头是标题链，信息密度最高的部分在前 300 字符，
# 截断后单条打分耗时显著下降（实测 10 候选 671ms -> 461ms），且指标不降。
RERANK_MAX_CHARS = 300


class Reranker:
    def __init__(self, model_name: str = RERANK_MODEL_NAME, max_chars: int = RERANK_MAX_CHARS):
        self._model_name = model_name
        self._max_chars = max_chars
        self._model = None
        self._error = ""
        self._load_failed = False

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def error(self) -> str:
        return self._error

    def load(self) -> bool:
        """加载模型；失败只记录一次，避免每个请求都重试。"""
        if self._model is not None:
            return True
        if self._load_failed:
            return False
        try:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                self._model_name,
                max_length=512,
                local_files_only=True,
                device="cpu",
            )
            return True
        except Exception as exc:
            self._load_failed = True
            self._error = f"{type(exc).__name__}: {exc}"
            print(f"[reranker] 精排模型不可用，已降级为不精排：{self._error}", file=sys.stderr)
            traceback.print_exc()
            return False

    def reorder(self, query: str, passages: list[str]) -> Optional[list[int]]:
        """返回按精排分数降序的下标；模型不可用或异常时返回 None。"""
        if not passages:
            return []
        if not self.load():
            return None
        try:
            pairs = [[query, (p or "")[: self._max_chars]] for p in passages]
            scores = self._model.predict(pairs)
            order = sorted(range(len(passages)), key=lambda i: float(scores[i]), reverse=True)
            return order
        except Exception:
            self._error = "predict failed"
            traceback.print_exc()
            return None
