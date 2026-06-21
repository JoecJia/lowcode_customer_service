import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from config import DEBUG, MAX_AGENT_TURNS, MAX_TASK_CALLS, REPO_DIR
from services.llm_service import (
    Task,
    build_ssl_context,
    call_chat_completions_stream,
    parse_tasks,
)
from services.skill_service import dispatch_skill, format_task_result, get_system_messages


def _run_agent_turn(
    api_key: str,
    payload: dict,
    ssl_context,
    messages: list[dict],
    task_calls: int,
    last_task_fingerprints: list[str],
) -> tuple[int, bool]:
    try:
        assistant_content, assistant_reasoning = call_chat_completions_stream(api_key, payload, ssl_context)
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return task_calls, True

    if assistant_content or assistant_reasoning:
        assistant_msg = {"role": "assistant", "content": assistant_content}
        if assistant_reasoning:
            assistant_msg["reasoning_content"] = assistant_reasoning
        messages.append(assistant_msg)

    combined = (assistant_content or "") + "\n" + (assistant_reasoning or "")
    tasks = parse_tasks(combined)
    if DEBUG:
        print(
            f"\n[debug] assistant_content_len={len(assistant_content or '')} "
            f"assistant_reasoning_len={len(assistant_reasoning or '')} tasks={len(tasks)}",
            file=sys.stderr,
        )
    if not tasks:
        return task_calls, False

    for task in tasks:
        task_calls += 1
        if task_calls > MAX_TASK_CALLS:
            print("\n[ABORT] Too many task calls, stop to avoid loop.\n", file=sys.stderr)
            return task_calls, False

        fingerprint = f"{task.task_type}|{task.query}|{task.top_k}"
        last_task_fingerprints.append(fingerprint)
        if len(last_task_fingerprints) >= 4 and len(set(last_task_fingerprints[-3:])) == 1:
            print("\n[ABORT] Repeated same task 3 times, stop to avoid loop.\n", file=sys.stderr)
            return task_calls, False

        result_text = dispatch_skill(REPO_DIR, task)

        sys.stdout.write("\n\n[task executed]\n")
        sys.stdout.flush()

        messages.append(format_task_result(task.task_type, result_text))
        if DEBUG:
            print("[debug] task_result appended, will ask model to continue", file=sys.stderr)

    return task_calls, True


def main() -> int:
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        print("Missing env var ARK_API_KEY", file=sys.stderr)
        return 2

    messages: list[dict] = get_system_messages()
    ssl_context = build_ssl_context()

    print("智能客服已就绪。输入您的问题，输入 /exit 退出。")
    print("-" * 50)

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            return 0

        if user_input.lower() in ("/exit", "/quit"):
            print("再见！")
            return 0
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        task_calls = 0
        last_task_fingerprints: list[str] = []

        for turn in range(MAX_AGENT_TURNS):
            payload = {
                "model": "doubao-seed-2-0-pro-260215",
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},
                "thinking": {"type": "enabled"},
            }

            task_calls, should_continue = _run_agent_turn(
                api_key, payload, ssl_context, messages, task_calls, last_task_fingerprints
            )
            if not should_continue:
                break

        if turn >= MAX_AGENT_TURNS - 1 and task_calls > 0:
            print(
                "\n[WARN] 当前问题已达到最大推理轮次，可能未完全回答。您可以继续追问。",
                file=sys.stderr,
            )


if __name__ == "__main__":
    raise SystemExit(main())
