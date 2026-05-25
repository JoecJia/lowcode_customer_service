import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from skills.context_transformation.vectorizer import (
    REPO_DIR,
    EmbeddingModel,
    build_index_from_docs,
    iter_md_files,
    save_chunk_meta,
)


def main() -> int:
    print(f"Repo dir: {REPO_DIR}")
    print("Scanning for .md files in context/ and skills/ ...")

    md_files = iter_md_files(REPO_DIR)
    print(f"Found {len(md_files)} .md file(s):")
    for f in md_files:
        print(f"  {os.path.relpath(f, REPO_DIR)}")

    if not md_files:
        print("No .md files found. Nothing to index.", file=sys.stderr)
        return 1

    print("\nLoading embedding model (first run will download ~100MB)...")
    t0 = time.time()
    embedder = EmbeddingModel()
    print(f"Model loaded in {time.time() - t0:.1f}s")

    print("Building FAISS index...")
    t0 = time.time()
    index_mgr, meta = build_index_from_docs(md_files, embedder=embedder)
    elapsed = time.time() - t0

    n_chunks = len(meta["chunks"])
    n_files = len(meta["file_index"])
    print(f"Done in {elapsed:.1f}s: {n_chunks} chunks across {n_files} files")

    print("Saving index and metadata...")
    index_mgr.save()
    save_chunk_meta(meta)
    print("Saved:")
    print(f"  index  -> context/.faiss/index.faiss")
    print(f"  meta   -> context/.faiss/chunk_meta.json")
    print(f"  vectors: {index_mgr.ntotal}")

    print("\nPhase 1 complete. Index is ready for hybrid search.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
