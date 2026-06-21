"""
分析大模型返回内容的模块结构。
用三个典型问题测试，记录 reasoning_content 和 content 的原始输出，
以便明确思考过程与最终回答的分界点。
"""
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from services.llm_service import build_ssl_context, stream_chat_completions

TEST_QUESTIONS = [
    "数据推送是什么",
    "数据联动怎么用？",
    "帮我搭建一个资产管理系统，只有一个管理员角色，要实现资产的入库、出库和盘点",
]

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_single_question(api_key: str, question: str, index: int) -> dict:
    """发送一个问题并记录完整的原始输出"""
    ssl_context = build_ssl_context()
    
    messages = [
        {"role": "system", "content": "你是超星低代码平台的智能客服助手。请根据你的知识回答用户问题。"},
        {"role": "user", "content": question},
    ]
    
    payload = {
        "model": "doubao-seed-2-0-pro-260215",
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "thinking": {"type": "enabled"},
    }

    reasoning_parts = []
    content_parts = []
    delta_log = []  # 记录每个 delta 的类型和长度

    print(f"\n{'='*60}")
    print(f"问题 {index+1}: {question}")
    print(f"{'='*60}")

    saw_reasoning = False
    saw_content = False

    for delta_type, text in stream_chat_completions(api_key, payload, ssl_context):
        if delta_type == "reasoning":
            if not saw_reasoning:
                saw_reasoning = True
                print("\n>>> [reasoning_content 开始]")
            reasoning_parts.append(text)
            delta_log.append({"type": "reasoning", "len": len(text)})
        elif delta_type == "content":
            if not saw_content:
                saw_content = True
                print(">>> [reasoning_content 结束]")
                print(">>> [content 开始]")
            content_parts.append(text)
            delta_log.append({"type": "content", "len": len(text)})
        elif delta_type == "error":
            print(f"\nERROR: {text}")
            return {"error": text}

    print(">>> [content 结束]")
    print()

    full_reasoning = "".join(reasoning_parts)
    full_content = "".join(content_parts)

    # 打印摘要
    if full_reasoning:
        print(f"--- reasoning_content 预览 (前200字符) ---")
        print(full_reasoning[:200])
        print("...")
    if full_content:
        print(f"--- content 预览 (前500字符) ---")
        print(full_content[:500])
        if len(full_content) > 500:
            print("...")
    else:
        print("--- content 为空 ---")

    result = {
        "question": question,
        "reasoning_length": len(full_reasoning),
        "content_length": len(full_content),
        "reasoning_preview": full_reasoning[:500] + ("..." if len(full_reasoning) > 500 else ""),
        "content_preview": full_content[:500] + ("..." if len(full_content) > 500 else ""),
        "full_reasoning": full_reasoning,
        "full_content": full_content,
        "delta_count": {"reasoning": len(reasoning_parts), "content": len(content_parts)},
    }

    # 分析 content 的模块结构
    modules = analyze_content_modules(full_content)
    result["modules"] = modules

    # 保存完整输出到文件
    output_file = os.path.join(OUTPUT_DIR, f"question_{index+1}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 保存纯文本版本
    txt_file = os.path.join(OUTPUT_DIR, f"question_{index+1}.txt")
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(f"问题: {question}\n")
        f.write(f"{'='*60}\n")
        f.write(f"\n--- reasoning_content ({len(full_reasoning)} chars) ---\n")
        f.write(full_reasoning)
        f.write(f"\n\n--- content ({len(full_content)} chars) ---\n")
        f.write(full_content)

    print(f"\n分析结果:")
    print(f"  reasoning_content: {len(full_reasoning)} chars, {len(reasoning_parts)} deltas")
    print(f"  content: {len(full_content)} chars, {len(content_parts)} deltas")
    print(f"  content 模块: {modules}")
    print(f"  已保存到: {output_file}")
    print(f"  纯文本版本: {txt_file}")

    return result


def analyze_content_modules(content: str) -> list[str]:
    """分析 content 中包含哪些模块"""
    import re
    modules = []
    content_lower = content.lower()

    if "<task>" in content_lower or "</task>" in content_lower:
        modules.append("task_block")
    if "[" in content and "]" in content:
        # 检查是否是 JSON 任务数组
        m = re.search(r'\[\s*\{[^}]*"[nt]', content)
        if m:
            modules.append("json_task_array")
    if content_lower.startswith("<think>") or " response" in content_lower[:100]:
        modules.append("xml_think_tag")
    
    # 分析是否有实际的回答内容
    cleaned = content
    cleaned = re.sub(r'<task>[\s\S]*?</task>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\[\s*\{\s*"(?:name|type|task_type)"[^\]]*\]', '', cleaned)
    cleaned = cleaned.strip()
    
    if cleaned:
        modules.append("actual_answer")
    
    return modules


def main():
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        print("缺少 ARK_API_KEY 环境变量", file=sys.stderr)
        return 2

    all_results = []
    for i, question in enumerate(TEST_QUESTIONS):
        result = run_single_question(api_key, question, i)
        all_results.append(result)

    # 汇总分析
    print(f"\n{'='*60}")
    print("汇总分析")
    print(f"{'='*60}")
    
    summary_file = os.path.join(OUTPUT_DIR, "summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    for r in all_results:
        print(f"\n问题: {r['question']}")
        print(f"  reasoning: {r['reasoning_length']} chars")
        print(f"  content: {r['content_length']} chars")
        print(f"  模块: {r.get('modules', [])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
