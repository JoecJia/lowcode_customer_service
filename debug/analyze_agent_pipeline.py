"""
完整 agent pipeline 分析脚本。
使用真实的 system message (agent.md + TOOL_PROTOCOL)，模拟 agent loop，
捕获并分析模型的 reasoning_content 和 content 原始输出。
"""
import json
import os
import sys
import ssl

from dotenv import load_dotenv

load_dotenv()

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "agent_config"))

from config import DEBUG, MAX_AGENT_TURNS, MAX_TASK_CALLS, REPO_DIR
from services.llm_service import (
    Task,
    build_ssl_context,
    parse_tasks,
    stream_chat_completions,
    find_task_blocks,
)
from services.skill_service import dispatch_skill, format_task_result, get_system_messages

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TEST_QUESTIONS = [
    "数据推送是什么",
    "数据联动怎么用？",
    "帮我搭建一个资产管理系统，只有一个管理员角色，要实现资产的入库、出库和盘点",
]


def run_agent_with_question(api_key: str, question: str, index: int):
    """用完整的 agent pipeline 运行一个问题，记录所有轮次的输出"""
    ssl_context = build_ssl_context()
    messages = get_system_messages()
    messages.append({"role": "user", "content": question})

    turns_log = []
    task_calls = 0
    last_task_fingerprints = []

    print(f"\n{'='*60}")
    print(f"问题 {index+1}: {question}")
    print(f"{'='*60}")

    for turn in range(MAX_AGENT_TURNS):
        print(f"\n--- Turn {turn} ---")
        
        payload = {
            "model": "doubao-seed-2-0-pro-260215",
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "thinking": {"type": "enabled"},
        }

        reasoning_parts = []
        content_parts = []
        turn_deltas = []

        saw_reasoning = False
        saw_content = False

        try:
            for delta_type, text in stream_chat_completions(api_key, payload, ssl_context):
                if delta_type == "reasoning":
                    if not saw_reasoning:
                        saw_reasoning = True
                        print("  [reasoning 开始]")
                    reasoning_parts.append(text)
                    turn_deltas.append({"type": "reasoning", "len": len(text)})
                elif delta_type == "content":
                    if not saw_content:
                        saw_content = True
                        if saw_reasoning:
                            print("  [reasoning 结束 → content 开始]")
                        else:
                            print("  [content 开始]")
                    content_parts.append(text)
                    turn_deltas.append({"type": "content", "len": len(text)})
                elif delta_type == "error":
                    print(f"  ERROR: {text}")
                    return {"error": text}
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            return {"error": str(e)}

        print(f"  [stream 结束]")

        full_reasoning = "".join(reasoning_parts)
        full_content = "".join(content_parts)

        # 分析这一轮的 content 结构
        task_blocks = find_task_blocks(full_content)
        tasks_parsed = parse_tasks(full_content + "\n" + full_reasoning)

        turn_info = {
            "turn": turn,
            "reasoning_length": len(full_reasoning),
            "content_length": len(full_content),
            "reasoning_preview": full_reasoning[:300] + ("..." if len(full_reasoning) > 300 else ""),
            "content_preview": full_content[:300] + ("..." if len(full_content) > 300 else ""),
            "full_reasoning": full_reasoning,
            "full_content": full_content,
            "task_blocks_found": len(task_blocks),
            "tasks_parsed": len(tasks_parsed),
            "task_blocks": task_blocks,
            "delta_count": {"reasoning": len(reasoning_parts), "content": len(content_parts)},
        }
        turns_log.append(turn_info)

        # 打印摘要
        print(f"  reasoning: {len(full_reasoning)} chars, content: {len(full_content)} chars")
        print(f"  <task> blocks in content: {len(task_blocks)}")
        print(f"  tasks parsed (content+reasoning): {len(tasks_parsed)}")
        
        if full_content:
            # 检查 content 中是否有非 task 内容
            import re
            cleaned = re.sub(r'<task>[\s\S]*?</task>', '', full_content, flags=re.IGNORECASE)
            cleaned = re.sub(r'\[\s*\{\s*"(?:name|type|task_type)"[^\]]*\]', '', cleaned)
            cleaned = cleaned.strip()
            print(f"  content after task removal: {len(cleaned)} chars")
            if cleaned:
                print(f"  cleaned preview: {cleaned[:200]}...")

        # 存储消息
        assistant_msg = {"role": "assistant", "content": full_content}
        if full_reasoning:
            assistant_msg["reasoning_content"] = full_reasoning
        messages.append(assistant_msg)

        # 解析任务
        combined = full_content + "\n" + full_reasoning
        tasks = parse_tasks(combined)

        if not tasks:
            print(f"  [无更多任务，agent loop 结束]")
            break

        # 执行任务
        for task in tasks:
            task_calls += 1
            if task_calls > MAX_TASK_CALLS:
                print(f"  [达到最大任务调用次数]")
                break

            fingerprint = f"{task.task_type}|{task.query}|{task.top_k}"
            last_task_fingerprints.append(fingerprint)
            if len(last_task_fingerprints) >= 4 and len(set(last_task_fingerprints[-3:])) == 1:
                print(f"  [检测到重复任务]")
                break

            result_text = dispatch_skill(REPO_DIR, task)
            print(f"  [skill 执行: {task.task_type}] 结果长度: {len(result_text)}")
            
            task_msg = format_task_result(task.task_type, result_text)
            messages.append(task_msg)

    # 保存结果
    result = {
        "question": question,
        "turns": turns_log,
        "total_turns": len(turns_log),
        "total_task_calls": task_calls,
    }
    
    output_file = os.path.join(OUTPUT_DIR, f"agent_question_{index+1}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n  结果已保存: {output_file}")
    return result


def main():
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        print("缺少 ARK_API_KEY", file=sys.stderr)
        return 2

    all_results = []
    for i, question in enumerate(TEST_QUESTIONS):
        result = run_agent_with_question(api_key, question, i)
        all_results.append(result)

    # 汇总
    print(f"\n{'='*60}")
    print("汇总分析")
    print(f"{'='*60}")
    
    for r in all_results:
        print(f"\n问题: {r['question']}")
        print(f"  总轮次: {r['total_turns']}")
        for t in r['turns']:
            print(f"  Turn {t['turn']}: reasoning={t['reasoning_length']}c, content={t['content_length']}c, tasks={t['tasks_parsed']}")

    summary_file = os.path.join(OUTPUT_DIR, "agent_summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
