#!/usr/bin/env python3
"""
文档转化流水线 (Document Transform Pipeline)
=============================================
将 .docx 文档转化为 Markdown Context，并自动压缩图片发布到 context/assets/。

流水线步骤：
  1. 解析 docx → 提取原始图片到 context_transformation/extracted_assets/<doc_name>/
  2. 生成 .md 文件（图片引用指向 staging 目录）
  3. 压缩 staging 中的图片 → context/assets/<doc_name>/
  4. 重写 .md 中图片引用 → context/assets/<doc_name>/
  5. 增量更新向量索引（调用 update_index.py update）

用法：
  python3 transform_document.py <input.docx> [--output <output.md>] [--category <dir_name>]

示例：
  python3 agent_config/skills/context_transformation/transform_document.py \
      my_document.docx \
      --output context/product_docs/faq/my_doc.md \
      --category faq
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---- 路径配置 ----
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILL_DIR = Path(__file__).resolve().parent
STAGING_DIR = SKILL_DIR / "extracted_assets"       # 原始图片暂存区
ASSETS_DIR = PROJECT_ROOT / "agent_config" / "context" / "assets"  # 最终压缩图片目录
DOCX_TO_MD_SCRIPT = SKILL_DIR / "docx_to_md.py"
COMPRESS_SCRIPT = SKILL_DIR / "compress_assets.py"
UPDATE_INDEX_SCRIPT = SKILL_DIR / "update_index.py"


def run_docx_to_md(input_docx: Path, output_md: Path, assets_rel: str) -> int:
    """Step 1: 调用 docx_to_md.py 转换文档"""
    cmd = [
        sys.executable, str(DOCX_TO_MD_SCRIPT),
        str(input_docx),
        str(output_md),
        "--assets", assets_rel,
    ]
    print(f"[Step 1] 文档转换: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"错误: 文档转换失败 (exit code {result.returncode})", file=sys.stderr)
    return result.returncode


def run_compress(source_dir: Path, target_dir: Path) -> int:
    """Step 3: 调用 compress_assets.py pipeline 模式压缩图片"""
    cmd = [
        sys.executable, str(COMPRESS_SCRIPT),
        "--source", str(source_dir),
        "--target", str(target_dir),
    ]
    print(f"[Step 3] 图片压缩: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"错误: 图片压缩失败 (exit code {result.returncode})", file=sys.stderr)
    return result.returncode


def run_update_index(md_path: Path) -> int:
    """Step 5: 调用 update_index.py 增量更新向量索引"""
    cmd = [
        sys.executable, str(UPDATE_INDEX_SCRIPT),
        "update", str(md_path),
    ]
    print(f"[Step 5] 更新索引: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"警告: 索引更新失败 (exit code {result.returncode})", file=sys.stderr)
        print("  不影响文档生成，可稍后手动执行: python3 agent_config/skills/context_transformation/update_index.py update <file>", file=sys.stderr)
    return result.returncode


def rewrite_md_refs(md_path: Path, old_prefix: str, new_prefix: str):
    """Step 4: 重写 .md 中图片引用路径"""
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 替换 markdown 图片引用: ![alt](old_prefix/...)
    pattern = re.escape(old_prefix)
    new_content = re.sub(r'!\[([^\]]*)\]\(' + pattern + r'/([^)]+)\)', 
                         rf'![\1]({new_prefix}/\2)', content)

    if new_content != content:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"[Step 4] 引用重写: {old_prefix} → {new_prefix}")
    else:
        print(f"[Step 4] 引用重写: 无匹配引用，跳过")


def do_transform(input_docx: Path, output_md: Path, category: str, skip_index: bool = False):
    """
    执行完整流水线：
      原始图片暂存 → 生成md → 压缩图片到assets → 重写md引用 → 更新向量索引
    """
    doc_name = input_docx.stem

    # 暂存目录
    staging_abs = STAGING_DIR / doc_name
    # 计算 output_md 所在目录到暂存区的相对路径（给 docx_to_md.py 用）
    staging_rel = os.path.relpath(str(staging_abs), str(output_md.parent))

    # 最终 assets 目录
    final_assets_abs = ASSETS_DIR / category
    # 计算 output_md 所在目录到 assets 的相对路径
    final_assets_rel = os.path.relpath(str(final_assets_abs), str(output_md.parent))

    print("=" * 60)
    print(f"文档转化流水线: {input_docx.name}")
    print(f"  → 输出:       {output_md}")
    print(f"  → 暂存区:     {staging_abs}")
    print(f"  → 压缩发布到: {final_assets_abs}")
    print("=" * 60)

    # 清理旧暂存
    if staging_abs.exists():
        shutil.rmtree(staging_abs)
        print(f"清理旧暂存: {staging_abs}")

    # Step 1: docx → md (图片提取到 staging)
    rc = run_docx_to_md(input_docx, output_md, staging_rel)
    if rc != 0:
        sys.exit(rc)

    # Step 2: (如果有图片) 压缩 staging → context/assets/<category>/
    if not staging_abs.exists() or not any(staging_abs.rglob("*")):
        print("暂存区无图片，跳过压缩。")
    else:
        # Step 3: 压缩
        rc = run_compress(staging_abs, final_assets_abs)
        if rc != 0:
            sys.exit(rc)

        # Step 4: 重写 md 引用
        rewrite_md_refs(output_md, staging_rel, final_assets_rel)

    # 清理暂存
    if staging_abs.exists():
        shutil.rmtree(staging_abs)
        print(f"\n清理暂存: {staging_abs}")

    # Step 5: 更新向量索引
    if not skip_index:
        run_update_index(output_md)

    print(f"\n{'=' * 60}")
    print(f"流水线完成!")
    print(f"  Markdown:  {output_md}")
    print(f"  图片资源:  {final_assets_abs}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="文档转化流水线")
    parser.add_argument("input", type=Path, help="输入 .docx 文件路径")
    parser.add_argument("--output", "-o", type=Path, help="输出 .md 文件路径（默认: context/product_docs/<doc_name>.md）")
    parser.add_argument("--category", "-c", default=None, help="assets 子目录名（默认: 与 docx 文件名相同）")
    parser.add_argument("--skip-index", action="store_true", help="跳过向量索引更新步骤")
    args = parser.parse_args()

    input_docx = args.input.resolve()
    if not input_docx.exists():
        print(f"错误: 文件不存在: {input_docx}", file=sys.stderr)
        sys.exit(1)

    doc_name = input_docx.stem
    category = args.category or doc_name

    if args.output:
        output_md = args.output.resolve()
    else:
        output_md = (PROJECT_ROOT / "agent_config" / "context" / "product_docs" / f"{doc_name}.md").resolve()

    # 确保输出目录存在
    output_md.parent.mkdir(parents=True, exist_ok=True)

    do_transform(input_docx, output_md, category, skip_index=args.skip_index)


if __name__ == "__main__":
    main()
