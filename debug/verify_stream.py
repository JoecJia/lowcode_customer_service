"""简单验证流式输出的脚本 - 发送一个问题并实时打印回复"""
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from services.llm_service import build_ssl_context, stream_chat_completions


def main():
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        print("缺少 ARK_API_KEY", file=sys.stderr)
        return 2

    ssl_context = build_ssl_context()

    messages = [
        {"role": "system", "content": "你是一个智能客服助手。"},
        {"role": "user", "content": "你好，请简单介绍一下你自己"},
    ]

    payload = {
        "model": "doubao-seed-2-0-pro-260215",
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "thinking": {"type": "enabled"},
    }

    print(">>> 开始流式请求...")
    print()

    saw_think = False
    for delta_type, text in stream_chat_completions(api_key, payload, ssl_context):
        if delta_type == "reasoning":
            if not saw_think:
                saw_think = True
                sys.stdout.write(">>> [思考过程]\n")
            sys.stdout.write(text)
            sys.stdout.flush()
        elif delta_type == "content":
            if saw_think:
                sys.stdout.write("\n>>> [正式回答]\n")
                saw_think = False
            sys.stdout.write(text)
            sys.stdout.flush()
        elif delta_type == "error":
            print(f"\nERROR: {text}", file=sys.stderr)
            return 1

    if saw_think:
        sys.stdout.write("\n")
    print()
    print()
    print(">>> 流式输出完成 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
