import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from agent_config.skills.context_transformation.vectorizer import (
    REPO_DIR,
    EmbeddingModel,
    build_index_from_docs,
    iter_md_files,
    load_chunk_meta,
    save_chunk_meta,
    update_document,
)


def cmd_update(file_path: str) -> int:
    abs_path = file_path if os.path.isabs(file_path) else os.path.join(REPO_DIR, file_path)
    if not os.path.exists(abs_path):
        print(f"Error: file not found: {abs_path}", file=sys.stderr)
        return 1

    rel = os.path.relpath(abs_path, REPO_DIR)
    print(f"Updating index for: {rel}")

    t0 = time.time()
    ok = update_document(abs_path)
    elapsed = time.time() - t0

    if ok:
        from agent_config.skills.knowledge_retrieval.hybrid_search import refresh_searcher
        refresh_searcher()
        meta = load_chunk_meta()
        file_index = meta.get("file_index", {})
        chunk_ids = file_index.get(rel, [])
        print(f"OK ({elapsed:.1f}s): {len(chunk_ids)} chunk(s) for {rel}")
        return 0
    else:
        print(f"Failed after {elapsed:.1f}s", file=sys.stderr)
        return 1


def cmd_rebuild() -> int:
    print("Rebuilding full index...")
    md_files = iter_md_files(REPO_DIR)
    print(f"Found {len(md_files)} .md file(s)")

    t0 = time.time()
    embedder = EmbeddingModel()
    index_mgr, meta = build_index_from_docs(md_files, embedder=embedder)
    elapsed = time.time() - t0

    index_mgr.save()
    save_chunk_meta(meta)
    from skills.knowledge_retrieval.hybrid_search import refresh_searcher
    refresh_searcher()
    print(f"Done ({elapsed:.1f}s): {len(meta['chunks'])} chunks across {len(meta['file_index'])} files")
    return 0


def cmd_status() -> int:
    meta = load_chunk_meta()
    n_chunks = len(meta.get("chunks", []))
    n_files = len(meta.get("file_index", {}))
    print(f"Index status: {n_chunks} chunks across {n_files} files")
    return 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Vector index maintenance tool")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    update_parser = subparsers.add_parser("update", help="Update index for a single file")
    update_parser.add_argument("file", help="Path to the .md file (absolute or relative to repo root)")

    subparsers.add_parser("rebuild", help="Rebuild entire index from scratch")
    subparsers.add_parser("status", help="Show current index status")

    args = parser.parse_args()

    if args.command == "update":
        return cmd_update(args.file)
    elif args.command == "rebuild":
        return cmd_rebuild()
    elif args.command == "status":
        return cmd_status()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
