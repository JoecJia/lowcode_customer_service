import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FAISS_DIR = os.path.join(REPO_DIR, "agent_config", "context", ".faiss")
INDEX_PATH = os.path.join(FAISS_DIR, "index.faiss")
META_PATH = os.path.join(FAISS_DIR, "chunk_meta.json")

EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
CHUNK_MAX_CHARS = 500
CHUNK_OVERLAP_CHARS = 50


def to_rel_path(file_path: str) -> str:
    """转成相对仓库根目录的相对路径，并统一用 `/` 分隔。

    索引里只允许存相对路径：绝对路径会随机器/仓库位置失效，
    而 Windows 的 `\\` 分隔符在迁移到 Linux 后也会与检索侧的比较逻辑不一致。
    """
    return os.path.relpath(file_path, REPO_DIR).replace(os.sep, "/")


@dataclass
class Chunk:
    chunk_id: int
    source_file: str
    header_chain: str
    content: str
    images: list[dict] = field(default_factory=list)


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def iter_md_files(base_dir: str) -> list[str]:
    roots = [
        os.path.join(base_dir, "agent_config", "context"),
        os.path.join(base_dir, "agent_config", "skills"),
    ]
    md_files: list[str] = []
    skip_dirs = {".faiss", ".staging", ".backup"}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # 剪枝：连遍历都不进入暂存区/备份区/索引目录，
            # 否则全量重建会把未确认草稿与历史备份写入索引（见开发文档 §11.9）
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fn in filenames:
                if fn.lower().endswith(".md"):
                    md_files.append(os.path.join(dirpath, fn))
    return md_files


class MarkdownChunker:
    def chunk_file(self, file_path: str) -> list[Chunk]:
        text = read_text_file(file_path)
        rel_path = to_rel_path(file_path)

        sections = self._split_by_headers(text)
        chunks: list[Chunk] = []
        for header_chain, body in sections:
            sub_chunks = self._split_long_body(header_chain, body)
            chunks.extend(sub_chunks)

        for i, chunk in enumerate(chunks):
            chunk.source_file = rel_path
            chunk.chunk_id = i

        self._apply_overlap(chunks)
        return chunks

    def _split_by_headers(self, text: str) -> list[tuple[str, str]]:
        lines = text.splitlines()
        sections: list[tuple[str, str]] = []
        current_headers: list[tuple[int, str]] = []
        current_lines: list[str] = []

        for line in lines:
            m = re.match(r"^(#{1,6})\s+(.+)", line)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()

                if current_lines:
                    header_chain = self._format_header_chain(current_headers)
                    sections.append((header_chain, "\n".join(current_lines).strip()))
                    current_lines = []

                current_headers = [h for h in current_headers if h[0] < level]
                current_headers.append((level, title))
                current_lines.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            header_chain = self._format_header_chain(current_headers)
            sections.append((header_chain, "\n".join(current_lines).strip()))

        return sections

    def _format_header_chain(self, headers: list[tuple[int, str]]) -> str:
        if not headers:
            return ""
        return " > ".join(title for _, title in headers)

    def _split_long_body(self, header_chain: str, body: str) -> list[Chunk]:
        if len(body) <= CHUNK_MAX_CHARS:
            images = self._extract_images(body)
            return [Chunk(chunk_id=-1, source_file="", header_chain=header_chain, content=body, images=images)]

        paragraphs = re.split(r"\n\s*\n", body)
        chunks: list[Chunk] = []
        current: list[str] = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > CHUNK_MAX_CHARS and current:
                content = "\n\n".join(current).strip()
                images = self._extract_images(content)
                chunks.append(Chunk(chunk_id=-1, source_file="", header_chain=header_chain, content=content, images=images))
                current = []
                current_len = 0
            current.append(para)
            current_len += para_len

        if current:
            content = "\n\n".join(current).strip()
            images = self._extract_images(content)
            chunks.append(Chunk(chunk_id=-1, source_file="", header_chain=header_chain, content=content, images=images))

        return chunks

    def _apply_overlap(self, chunks: list[Chunk]) -> None:
        for i in range(len(chunks) - 1):
            prev_content = chunks[i].content
            if len(prev_content) > CHUNK_OVERLAP_CHARS:
                overlap_text = prev_content[-CHUNK_OVERLAP_CHARS:]
                chunks[i + 1].content = overlap_text + "\n\n" + chunks[i + 1].content

    def _extract_images(self, text: str) -> list[dict]:
        seen = set()
        images = []
        valid_exts = {'.png', '.gif', '.jpeg', '.jpg'}
        # 使用 ([^()]+) 匹配 path，防止 alt 文本中的嵌套 markdown 链接（如 [text](url)）
        # 干扰图片路径提取，导致 path 包含错误的前缀内容。
        for alt, path in re.findall(r"!\[(.+?)\]\(([^()]+)\)", text):
            _, ext = os.path.splitext(path)
            if ext.lower() not in valid_exts:
                continue
            key = (alt, path)
            if key in seen:
                continue
            seen.add(key)
            images.append({"alt": alt, "path": path})
        return images


class EmbeddingModel:
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        import os as _os
        # 强制离线模式，避免服务器无外网时 SentenceTransformer 尝试联网检查 PEFT adapter 配置
        _os.environ.setdefault("HF_HUB_OFFLINE", "1")
        _os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        _os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer
        self._model_name = model_name
        self._model = SentenceTransformer(model_name, local_files_only=True)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dim(self) -> int:
        # sentence-transformers 新版本把 get_sentence_embedding_dimension 改名为 get_embedding_dimension
        getter = getattr(self._model, "get_embedding_dimension", None)
        if getter is None:
            getter = self._model.get_sentence_embedding_dimension
        return int(getter())

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        if is_query:
            texts = [f"为这个句子生成表示以用于检索相关文章：{t}" for t in texts]
        embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(embeddings, dtype=np.float32)


def check_index_compatibility(
    meta: dict,
    embedder: "EmbeddingModel",
    index_dim: Optional[int] = None,
) -> tuple[bool, str]:
    """校验 FAISS 索引（含 chunk_meta 中的模型信息）与当前 embedding 模型是否同源。

    返回 ``(是否兼容, 说明)``。不兼容意味着索引向量与 query 向量不在同一空间，
    搜索不会报错但结果不可信（同维度不同模型时尤其隐蔽），调用方应禁用向量通道
    或拒绝增量写入，并提示全量 rebuild。
    """
    model_dim = embedder.dim

    if index_dim and model_dim != index_dim:
        return False, f"向量维度不一致：索引 {index_dim} 维，模型 {embedder.model_name} 输出 {model_dim} 维"

    meta_model = meta.get("embedding_model")
    meta_dim = meta.get("embedding_dim")

    if meta_model and meta_model != embedder.model_name:
        return False, f"索引由 {meta_model} 构建，与当前模型 {embedder.model_name} 不一致"

    if meta_dim and int(meta_dim) != model_dim:
        return False, f"索引元数据记录 {meta_dim} 维，模型输出 {model_dim} 维"

    if not meta_model or not meta_dim:
        return True, "索引元数据未记录模型信息（旧版索引），已跳过模型一致性校验；建议执行 rebuild 补齐"

    return True, "索引与模型一致"


class FAISSIndexManager:
    def __init__(self, dim: Optional[int] = None):
        self._dim = dim
        self._index = None

    @property
    def index(self):
        return self._index

    @property
    def ntotal(self) -> int:
        return self._index.ntotal if self._index else 0

    @property
    def dim(self) -> Optional[int]:
        """索引实际维度；未加载/未构建时返回 None。"""
        return int(self._index.d) if self._index is not None else self._dim

    def build(self, vectors: np.ndarray) -> None:
        import faiss
        dim = vectors.shape[1] if vectors.shape[0] > 0 else (self._dim or 512)
        self._dim = dim
        self._index = faiss.IndexFlatIP(dim)
        if vectors.shape[0] > 0:
            self._index.add(vectors)

    def save(self, path: str = INDEX_PATH) -> None:
        import faiss
        import tempfile
        import shutil
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # FAISS C++ fopen 可能无法处理含全角字符的路径，先写临时文件再移动
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".faiss", prefix="faiss_")
        os.close(tmp_fd)
        try:
            faiss.write_index(self._index, tmp_path)
            shutil.move(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def load(self, path: str = INDEX_PATH) -> bool:
        import faiss
        import tempfile
        import shutil
        if not os.path.exists(path):
            return False
        # FAISS C++ fopen 可能无法处理含全角字符的路径，先复制到临时文件再读取
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".faiss", prefix="faiss_")
        os.close(tmp_fd)
        try:
            shutil.copy2(path, tmp_path)
            self._index = faiss.read_index(tmp_path)
            return True
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> tuple[np.ndarray, np.ndarray]:
        if self._index is None:
            return np.array([]), np.array([])
        query_vector = query_vector.reshape(1, -1).astype(np.float32)
        distances, indices = self._index.search(query_vector, min(top_k, self._index.ntotal))
        return distances[0], indices[0]

    def remove_ids(self, ids: list[int]) -> None:
        import faiss
        if self._index is None:
            return
        id_selector = faiss.IDSelectorArray(np.array(ids, dtype=np.int64))
        self._index.remove_ids(id_selector)


def load_chunk_meta(path: str = META_PATH) -> dict:
    if not os.path.exists(path):
        return {"chunks": [], "file_index": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_chunk_meta(meta: dict, path: str = META_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _chunk_to_dict(chunk: Chunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "source_file": chunk.source_file,
        "header_chain": chunk.header_chain,
        "content": chunk.content,
        "images": chunk.images,
    }


def _dict_to_chunk(d: dict) -> Chunk:
    return Chunk(
        chunk_id=d["chunk_id"],
        source_file=d["source_file"],
        header_chain=d["header_chain"],
        content=d["content"],
        images=d.get("images", []),
    )


def build_index_from_docs(
    md_files: list[str],
    embedder: Optional[EmbeddingModel] = None,
) -> tuple[FAISSIndexManager, dict]:
    if embedder is None:
        embedder = EmbeddingModel()

    chunker = MarkdownChunker()
    all_chunks: list[Chunk] = []
    file_index: dict[str, list[int]] = {}

    chunk_id_counter = 0
    for fpath in md_files:
        try:
            chunks = chunker.chunk_file(fpath)
        except Exception:
            continue
        if not chunks:
            continue
        file_ids = []
        for chunk in chunks:
            chunk.chunk_id = chunk_id_counter
            chunk.source_file = to_rel_path(fpath)
            all_chunks.append(chunk)
            file_ids.append(chunk_id_counter)
            chunk_id_counter += 1
        file_index[to_rel_path(fpath)] = file_ids

    if not all_chunks:
        index_mgr = FAISSIndexManager()
        index_mgr.build(np.empty((0, 0), dtype=np.float32))
        meta = {
            "embedding_model": embedder.model_name,
            "embedding_dim": embedder.dim,
            "chunks": [],
            "file_index": {},
        }
        return index_mgr, meta

    contents = [chunk.content for chunk in all_chunks]
    vectors = embedder.encode(contents, is_query=False)

    index_mgr = FAISSIndexManager()
    index_mgr.build(vectors)

    meta = {
        # 记录建索引所用的模型与维度：更换模型后若忘记重建，加载时可立即发现
        "embedding_model": embedder.model_name,
        "embedding_dim": int(vectors.shape[1]),
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "chunks": [_chunk_to_dict(c) for c in all_chunks],
        "file_index": file_index,
    }

    return index_mgr, meta


def update_document(file_path: str, embedder: Optional[EmbeddingModel] = None) -> bool:
    if embedder is None:
        embedder = EmbeddingModel()

    rel_path = to_rel_path(file_path)
    meta = load_chunk_meta()
    file_index = meta.get("file_index", {})

    if not os.path.exists(file_path):
        return False

    index_mgr = FAISSIndexManager()
    if not index_mgr.load():
        return False

    ok, reason = check_index_compatibility(meta, embedder, index_mgr.dim)
    if not ok:
        print(
            f"[vectorizer] 拒绝增量更新 {rel_path}：{reason}。"
            "索引与当前 embedding 模型不同源，请先执行 "
            "`update_index.py rebuild` 全量重建索引。",
            file=sys.stderr,
        )
        return False

    # 兼容旧版索引：借本次更新补齐元数据，后续即可严格校验
    meta["embedding_model"] = embedder.model_name
    meta["embedding_dim"] = embedder.dim

    old_ids = file_index.pop(rel_path, [])
    # 兼容历史索引中按反斜杠写入的键，否则会找不到旧条目并重复入库
    for legacy_key in [k for k in file_index if k.replace("\\", "/") == rel_path]:
        old_ids.extend(file_index.pop(legacy_key, []))
    if old_ids:
        # IndexFlat 的 remove_ids 按“向量位置”生效且会前移后续向量，
        # 而 chunk_id 是自增编号，删除过其他文件后二者不再相等，
        # 因此必须先把 chunk_id 换算成当前的实际位置再删除。
        old_id_set = set(old_ids)
        old_positions = [
            pos for pos, c in enumerate(meta["chunks"]) if c["chunk_id"] in old_id_set
        ]
        if old_positions:
            index_mgr.remove_ids(old_positions)
        meta["chunks"] = [c for c in meta["chunks"] if c["chunk_id"] not in old_id_set]

    chunker = MarkdownChunker()
    try:
        new_chunks = chunker.chunk_file(file_path)
    except Exception:
        save_chunk_meta(meta)
        index_mgr.save()
        return False

    if not new_chunks:
        # 文件存在但解析不出任何 chunk（空文件或异常格式）：旧条目已移除，需要显式告警
        print(f"[vectorizer] {rel_path} 分块结果为空，已从索引中移除", file=sys.stderr)
        save_chunk_meta(meta)
        index_mgr.save()
        return True

    max_id = max((c["chunk_id"] for c in meta["chunks"]), default=-1)
    new_ids = []
    new_vectors_list = []
    for chunk in new_chunks:
        max_id += 1
        chunk.chunk_id = max_id
        chunk.source_file = rel_path
        new_ids.append(max_id)
        meta["chunks"].append(_chunk_to_dict(chunk))
        new_vectors_list.append(chunk.content)

    vectors = embedder.encode(new_vectors_list, is_query=False)
    index_mgr.index.add(vectors)

    # 写入前的最后一道防线：向量数与元数据条目数必须一致，
    # 否则检索会因位置错位命中错误的 chunk 内容。
    if index_mgr.ntotal != len(meta["chunks"]):
        print(
            f"[vectorizer] 索引与元数据数量不一致（向量 {index_mgr.ntotal} / "
            f"元数据 {len(meta['chunks'])}），已放弃本次写入，请执行 "
            "`update_index.py rebuild` 全量重建。",
            file=sys.stderr,
        )
        return False

    file_index[rel_path] = new_ids
    meta["file_index"] = file_index

    save_chunk_meta(meta)
    index_mgr.save()
    return True


def search_similar(query: str, embedder: Optional[EmbeddingModel] = None, top_k: int = 5) -> list[dict]:
    if embedder is None:
        embedder = EmbeddingModel()

    index_mgr = FAISSIndexManager()
    if not index_mgr.load():
        return []

    meta = load_chunk_meta()
    chunks = meta.get("chunks", [])
    if not chunks:
        return []

    query_vector = embedder.encode([query], is_query=True)
    distances, indices = index_mgr.search(query_vector, top_k)

    results = []
    for dist, idx in zip(distances, indices):
        if idx < 0 or idx >= len(chunks):
            continue
        chunk = dict(chunks[idx])
        chunk["score"] = float(dist)
        results.append(chunk)

    return results
