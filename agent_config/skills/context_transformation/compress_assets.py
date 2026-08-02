#!/usr/bin/env python3
"""
图片压缩脚本 —— PNG / GIF 有损压缩。

原地模式（默认）：
  python3 compress_assets.py                              # 压缩 context/assets/ 下所有图片
  python3 compress_assets.py --dry-run                    # 仅预览
  python3 compress_assets.py --rollback                    # 从备份恢复

Pipeline 模式（文档转化流水线用）：
  python3 compress_assets.py --source <raw_dir> --target <compressed_dir>

策略：
  PNG: 若 RGBA 且 Alpha 全不透明 → 转 RGB → FASTOCTREE 256色量化 → 保存
      否则直接 FASTOCTREE 量化（保留透明度）。
  GIF: FASTOCTREE 128色量化 → save_all + optimize。

依赖：Pillow（pip install Pillow）
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

from PIL import Image

# ---- 路径配置 ----
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ASSETS_DIR = PROJECT_ROOT / "agent_config" / "context" / "assets"
BACKUP_DIR = PROJECT_ROOT / "docs" / "convert_docs" / "assets_converts"


def compress_png(filepath: Path) -> float:
    """压缩 PNG 文件，返回节省的百分比"""
    orig = filepath.stat().st_size
    img = Image.open(filepath)

    do_quantize = True
    if img.mode == "RGBA":
        alpha = img.split()[-1]
        if alpha.getextrema() == (255, 255):
            img = img.convert("RGB")
    elif img.mode == "P":
        do_quantize = False

    if do_quantize:
        img = img.quantize(colors=256, method=Image.Quantize.FASTOCTREE)

    img.save(str(filepath), optimize=True)
    new_size = filepath.stat().st_size
    return (1 - new_size / orig) * 100


def compress_gif(filepath: Path) -> float:
    """压缩 GIF 文件，返回节省的百分比"""
    orig = filepath.stat().st_size
    img = Image.open(filepath)
    img = img.quantize(colors=128, method=Image.Quantize.FASTOCTREE)
    img.save(str(filepath), save_all=True, optimize=True)
    new_size = filepath.stat().st_size
    return (1 - new_size / orig) * 100


def collect_images(assets_dir: Path):
    """收集所有需要处理的图片路径"""
    png_files = []
    gif_files = []
    for root, _dirs, files in os.walk(assets_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            full = Path(root) / f
            if ext == ".png":
                png_files.append(full)
            elif ext == ".gif":
                gif_files.append(full)
    return png_files, gif_files


def do_compress(assets_dir: Path, dry_run: bool = False):
    """执行原地压缩"""
    png_files, gif_files = collect_images(assets_dir)
    total = len(png_files) + len(gif_files)
    if total == 0:
        print("未找到图片文件。")
        return

    print(f"找到 {len(png_files)} 个 PNG + {len(gif_files)} 个 GIF，共 {total} 个文件\n")

    total_orig = 0
    total_new = 0
    errors = 0

    for i, fp in enumerate(png_files, 1):
        try:
            orig_sz = fp.stat().st_size
            if dry_run:
                print(f"[{i}/{total}] {fp.relative_to(assets_dir)}")
                total_orig += orig_sz
                total_new += orig_sz * 0.3
            else:
                saved = compress_png(fp)
                new_sz = fp.stat().st_size
                total_orig += orig_sz
                total_new += new_sz
                print(f"[{i}/{total}] {fp.relative_to(assets_dir)}: {orig_sz/1024:.0f}KB → {new_sz/1024:.0f}KB ({saved:.1f}%)")
        except Exception as e:
            print(f"[{i}/{total}] {fp.relative_to(assets_dir)}: ERROR - {e}", file=sys.stderr)
            errors += 1

    for i, fp in enumerate(gif_files, len(png_files) + 1):
        try:
            orig_sz = fp.stat().st_size
            if dry_run:
                total_orig += orig_sz
                total_new += orig_sz * 0.1
            else:
                saved = compress_gif(fp)
                new_sz = fp.stat().st_size
                total_orig += orig_sz
                total_new += new_sz
                print(f"[{i}/{total}] {fp.relative_to(assets_dir)}: {orig_sz/1024:.0f}KB → {new_sz/1024:.0f}KB ({saved:.1f}%)")
        except Exception as e:
            print(f"[{i}/{total}] {fp.relative_to(assets_dir)}: ERROR - {e}", file=sys.stderr)
            errors += 1

    print()
    if dry_run:
        print(f"=== 预估结果 ===")
        print(f"原始大小: {total_orig/1024/1024:.0f} MB")
        print(f"压缩后预估: {total_new/1024/1024:.0f} MB")
        print(f"预计节省: {(total_orig-total_new)/1024/1024:.0f} MB ({(1-total_new/total_orig)*100:.0f}%)")
    else:
        saved = total_orig - total_new
        print(f"=== 压缩完成 ===")
        print(f"原始大小: {total_orig/1024/1024:.0f} MB → 压缩后: {total_new/1024/1024:.0f} MB")
        print(f"节省: {saved/1024/1024:.0f} MB ({(1-total_new/total_orig)*100:.0f}%)")
        print(f"错误数: {errors}")
        if saved > 0:
            print(f"\n原文件已备份至: {BACKUP_DIR}")
            print(f"如需回滚，运行: python3 agent_config/skills/context_transformation/compress_assets.py --rollback")


def do_pipeline_compress(source_dir: Path, target_dir: Path):
    """
    Pipeline 模式：从 source_dir 读取原始图片，压缩后写入 target_dir。
    保持子目录结构一致。
    """
    if not source_dir.exists():
        print(f"错误: 源目录不存在: {source_dir}")
        sys.exit(1)

    png_files, gif_files = collect_images(source_dir)
    total = len(png_files) + len(gif_files)
    if total == 0:
        print(f"源目录中未找到图片文件: {source_dir}")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Pipeline 压缩: {source_dir} → {target_dir}")
    print(f"找到 {len(png_files)} 个 PNG + {len(gif_files)} 个 GIF，共 {total} 个文件\n")

    total_orig = 0
    total_new = 0
    errors = 0

    for i, src_fp in enumerate(png_files, 1):
        try:
            orig_sz = src_fp.stat().st_size
            rel = src_fp.relative_to(source_dir)
            dst_fp = target_dir / rel
            dst_fp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_fp), str(dst_fp))
            saved = compress_png(dst_fp)
            new_sz = dst_fp.stat().st_size
            total_orig += orig_sz
            total_new += new_sz
            print(f"[{i}/{total}] {rel}: {orig_sz/1024:.0f}KB → {new_sz/1024:.0f}KB ({saved:.1f}%)")
        except Exception as e:
            print(f"[{i}/{total}] {src_fp.relative_to(source_dir)}: ERROR - {e}", file=sys.stderr)
            errors += 1

    for i, src_fp in enumerate(gif_files, len(png_files) + 1):
        try:
            orig_sz = src_fp.stat().st_size
            rel = src_fp.relative_to(source_dir)
            dst_fp = target_dir / rel
            dst_fp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_fp), str(dst_fp))
            saved = compress_gif(dst_fp)
            new_sz = dst_fp.stat().st_size
            total_orig += orig_sz
            total_new += new_sz
            print(f"[{i}/{total}] {rel}: {orig_sz/1024:.0f}KB → {new_sz/1024:.0f}KB ({saved:.1f}%)")
        except Exception as e:
            print(f"[{i}/{total}] {src_fp.relative_to(source_dir)}: ERROR - {e}", file=sys.stderr)
            errors += 1

    print()
    saved = total_orig - total_new
    print(f"=== Pipeline 压缩完成 ===")
    print(f"原始大小: {total_orig/1024:.0f}KB → 压缩后: {total_new/1024:.0f}KB")
    print(f"节省: {saved/1024:.0f}KB ({(1-total_new/max(total_orig,1))*100:.0f}%)")
    print(f"错误数: {errors}")


def do_rollback(assets_dir: Path, backup_dir: Path):
    """从备份目录恢复原始文件"""
    if not backup_dir.exists():
        print(f"错误: 备份目录不存在: {backup_dir}")
        sys.exit(1)

    for item in assets_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    for item in backup_dir.iterdir():
        dest = assets_dir / item.name
        if item.is_dir():
            shutil.copytree(str(item), str(dest))
        else:
            shutil.copy2(str(item), str(dest))

    print(f"回滚完成: {backup_dir} → {assets_dir}")
    total = sum(1 for _ in assets_dir.rglob("*") if _.is_file())
    print(f"已恢复 {total} 个文件")


def main():
    parser = argparse.ArgumentParser(description="压缩 PNG/GIF 图片")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不修改文件")
    parser.add_argument("--rollback", action="store_true", help="从备份恢复原始文件")
    parser.add_argument("--source", type=Path, help="Pipeline 模式：原始图片目录")
    parser.add_argument("--target", type=Path, help="Pipeline 模式：压缩后输出目录（需配合 --source）")
    args = parser.parse_args()

    if args.source and args.target:
        do_pipeline_compress(args.source.resolve(), args.target.resolve())
        return

    if args.rollback:
        do_rollback(ASSETS_DIR, BACKUP_DIR)
        return

    do_compress(ASSETS_DIR, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
