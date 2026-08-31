"""反馈表填写链接生成脚本：对 precast 参数做 URL 编码并拼接完整链接。

编码逻辑统一由本脚本处理（UTF-8 URL 编码），大模型不得自行手工编码。

CLI 用法：
    python build_link.py --base-url "http://office.chaoxing.com/front/web/apps/forms/fore/apply?id=154231&..." \
        --precast '{"data":[{"alias":"products","compt":"checklist","val":[{"val":"表单"}]}]}'
    python build_link.py --base-url "<基础链接>" --precast-file precast.json

代码级调用：
    from skills.feedback_form_link.build_link import build_feedback_form_link
    url = build_feedback_form_link(base_url, precast)
"""

import argparse
import json
import sys
from urllib.parse import quote


def encode_precast(precast: dict) -> str:
    """将 precast JSON 序列化并做 URL 编码（UTF-8，safe="" 编码所有保留字符）。"""
    raw = json.dumps(precast, ensure_ascii=False, separators=(",", ":"))
    return quote(raw, safe="")


def build_feedback_form_link(base_url: str, precast: dict) -> str:
    """拼接完整链接：<base_url>&precast=<URL编码后的JSON>。

    若 base_url 不含任何查询参数，则使用 ? 作为分隔符；
    否则使用 & 追加，且不改动 base_url 中已有的任何参数。
    """
    if not isinstance(precast, dict):
        raise TypeError("precast 必须是 JSON 对象")
    encoded = encode_precast(precast)
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}precast={encoded}"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成反馈表填写链接（precast 自动 URL 编码）")
    parser.add_argument("--base-url", required=True, help="office-mcp 返回的反馈表填写页面基础链接")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--precast", help="precast JSON 字符串")
    group.add_argument("--precast-file", help="precast JSON 文件路径")
    args = parser.parse_args()

    if args.precast_file:
        try:
            with open(args.precast_file, "r", encoding="utf-8") as f:
                precast = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"读取 precast 文件失败: {e}", file=sys.stderr)
            return 1
    else:
        try:
            precast = json.loads(args.precast)
        except json.JSONDecodeError as e:
            print(f"解析 precast JSON 失败: {e}", file=sys.stderr)
            return 1

    if not isinstance(precast, dict):
        print("precast 必须是 JSON 对象", file=sys.stderr)
        return 1

    try:
        print(build_feedback_form_link(args.base_url, precast))
    except Exception as e:
        print(f"生成链接失败: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
