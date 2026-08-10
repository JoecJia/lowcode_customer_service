"""知识检索诊断脚本 —— 在服务器上运行，逐项排查检索失败原因"""
import os
import sys
import traceback

# 确保 agent_config 在 sys.path 中（与 main.py 一致）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

PASS = "  PASS"
FAIL = "  FAIL"
SKIP = "  SKIP"

def check(name: str, ok: bool, detail: str = "") -> bool:
    status = PASS if ok else FAIL
    msg = f"[{status}] {name}"
    if detail:
        msg += f" ({detail})"
    print(msg)
    return ok


def main():
    print("=" * 60)
    print("知识检索诊断")
    print("=" * 60)

    # ── 1. 依赖检查 ──
    print("\n── 1. Python 依赖 ──")
    deps = {
        "faiss": "faiss",
        "jieba": "jieba",
        "rank_bm25": "rank_bm25",
        "sentence_transformers": "sentence_transformers",
        "numpy": "numpy",
    }
    all_deps_ok = True
    for import_name, pip_name in deps.items():
        try:
            __import__(import_name)
            check(pip_name, True)
        except ImportError:
            check(pip_name, False, f"pip install {pip_name}")
            all_deps_ok = False

    if not all_deps_ok:
        print("\n请先安装缺失依赖: pip install -r backend/requirements.txt")
        return

    # ── 2. 索引文件检查 ──
    print("\n── 2. 索引文件 ──")
    from agent_config.skills.context_transformation.vectorizer import INDEX_PATH, META_PATH, REPO_DIR

    print(f"  项目根目录: {REPO_DIR}")
    check("index.faiss 存在", os.path.exists(INDEX_PATH), INDEX_PATH)
    check("chunk_meta.json 存在", os.path.exists(META_PATH), META_PATH)

    if not os.path.exists(INDEX_PATH) or not os.path.exists(META_PATH):
        print("\n索引文件缺失。请在项目根目录运行:")
        print("  python agent_config/skills/context_transformation/build_initial_index.py")
        return

    # 文件大小
    index_size = os.path.getsize(INDEX_PATH)
    meta_size = os.path.getsize(META_PATH)
    print(f"  index.faiss 大小: {index_size / 1024:.0f} KB ({index_size} bytes)")
    print(f"  chunk_meta.json 大小: {meta_size / 1024:.0f} KB ({meta_size} bytes)")

    # ── 3. FAISS 索引加载 ──
    print("\n── 3. FAISS 索引加载 ──")
    try:
        from agent_config.skills.context_transformation.vectorizer import FAISSIndexManager
        mgr = FAISSIndexManager()
        loaded = mgr.load()
        check("FAISS 索引加载", loaded)
        if loaded:
            check(f"向量数量 > 0 (当前: {mgr.ntotal})", mgr.ntotal > 0)
        else:
            print("  FAISS read_index 失败，可能文件损坏或版本不兼容")
    except Exception as e:
        check("FAISS 索引加载", False, str(e))
        traceback.print_exc()

    # ── 4. chunk_meta 解析 ──
    print("\n── 4. chunk_meta 解析 ──")
    try:
        from agent_config.skills.context_transformation.vectorizer import load_chunk_meta
        meta = load_chunk_meta()
        chunks = meta.get("chunks", [])
        files = meta.get("file_index", {})
        check("chunks 非空", len(chunks) > 0, f"{len(chunks)} 个 chunk")
        check("file_index 非空", len(files) > 0, f"{len(files)} 个文件")
        if chunks:
            sample = chunks[0]
            print(f"  首个 chunk: source={sample.get('source_file','?')}, content_len={len(sample.get('content',''))}")
    except Exception as e:
        check("chunk_meta 解析", False, str(e))
        traceback.print_exc()

    # ── 5. Embedding 模型加载 ──
    print("\n── 5. Embedding 模型 (BAAI/bge-small-zh-v1.5) ──")
    try:
        from agent_config.skills.context_transformation.vectorizer import EmbeddingModel
        embedder = EmbeddingModel()
        test_vec = embedder.encode(["测试"], is_query=True)
        check("模型加载并推理成功", test_vec.shape[0] == 1, f"shape={test_vec.shape}")
    except Exception as e:
        check("模型加载", False, str(e))
        traceback.print_exc()

    # ── 6. BM25 检索器 ──
    print("\n── 6. BM25 检索器 ──")
    try:
        from agent_config.skills.knowledge_retrieval.hybrid_search import BM25Retriever
        bm25 = BM25Retriever()
        results = bm25.search("数据导出", top_k=3)
        check("BM25 检索", len(results) > 0, f"命中 {len(results)} 条")
    except Exception as e:
        check("BM25 检索", False, str(e))
        traceback.print_exc()

    # ── 7. 向量检索器 ──
    print("\n── 7. 向量检索器 ──")
    try:
        from agent_config.skills.knowledge_retrieval.hybrid_search import VectorRetriever
        vr = VectorRetriever()
        check("VectorRetriever.ready", vr.ready)
        results = vr.search("数据导出", top_k=3)
        check("向量检索", len(results) > 0, f"命中 {len(results)} 条")
    except Exception as e:
        check("向量检索", False, str(e))
        traceback.print_exc()

    # ── 8. 混合检索 (完整链路) ──
    print("\n── 8. 混合检索 (完整链路) ──")
    try:
        from agent_config.skills.knowledge_retrieval.hybrid_search import HybridSearcher, refresh_searcher
        refresh_searcher()  # 确保全新初始化
        searcher = HybridSearcher()
        check("HybridSearcher.ready", searcher.ready)
        results = searcher.search("数据导出", top_k=3)
        check("混合检索命中", len(results) > 0, f"命中 {len(results)} 条")
        for i, r in enumerate(results):
            src = r.get("source_file", "?")
            header = r.get("header_chain", "")
            content_preview = r.get("content", "")[:80].replace("\n", " ")
            print(f"  [{i+1}] {header} | {src}")
            print(f"       {content_preview}...")
    except Exception as e:
        check("混合检索", False, str(e))
        traceback.print_exc()

    # ── 9. retrieve() 函数 ──
    print("\n── 9. retrieve() 端到端 ──")
    try:
        from agent_config.skills.knowledge_retrieval.hybrid_search import retrieve, refresh_searcher
        refresh_searcher()
        result = retrieve("数据导出", top_k=3)
        hit_len = len(result.get("hit_text", ""))
        img_count = len(result.get("images", []))
        check("hit_text 非空", hit_len > 0, f"{hit_len} 字符")
        check("images", True, f"{img_count} 张")
        if hit_len == 0:
            print("  retrieve() 返回空，请检查以上各步骤的 FAIL 项")
    except Exception as e:
        check("retrieve()", False, str(e))
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
