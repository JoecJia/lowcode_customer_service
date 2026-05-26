import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


ARK_CHAT_COMPLETIONS_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

MAX_AGENT_TURNS = 6
MAX_TASK_CALLS = 10

SKILL_REGISTRY = {
    "knowledge_retrieval": "skills/knowledge_retrieval/knowledge_retrieval.md",
    "clarifying_questions": "skills/clarifying_questions.md",
    "product_feature_usage": "skills/product_feature_usage.md",
    "usage_scenarios": "skills/usage_scenarios.md",
    "scenario_solutions": "skills/scenario_solutions.md",
    "build_business_system": "skills/build_business_system.md",
    "git_sync": "skills/git_sync/git_sync.md",
    "context_transformation": "skills/context_transformation/context_transformation.md",
    "temporary_context_management": "skills/temporary_context_management.md",
}

DEBUG = os.environ.get("ARK_DEBUG", "").strip().lower() in {"1", "true", "yes"}


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def iter_sse_data_lines(response):
    while True:
        raw = response.readline()
        if not raw:
            return
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        if not line.startswith("data:"):
            continue
        yield line[len("data:") :].strip()


def build_ssl_context() -> ssl.SSLContext:
    insecure = os.environ.get("ARK_INSECURE", "").strip().lower() in {"1", "true", "yes"}
    if insecure:
        return ssl._create_unverified_context()

    ca_candidates = [
        os.environ.get("ARK_CA_BUNDLE", "").strip(),
        os.environ.get("SSL_CERT_FILE", "").strip(),
        "/etc/ssl/cert.pem",
        "/private/etc/ssl/cert.pem",
        "/opt/homebrew/etc/openssl@3/cert.pem",
        "/usr/local/etc/openssl@3/cert.pem",
        "/opt/homebrew/etc/openssl@1.1/cert.pem",
        "/usr/local/etc/openssl@1.1/cert.pem",
    ]
    cafile = next((p for p in ca_candidates if p and os.path.exists(p)), None)
    if cafile:
        return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()

@dataclass(frozen=True)
class Task:
    task_type: str
    raw: str
    query: str | None = None
    top_k: int | None = None


def find_task_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    lower = text.lower()
    start = 0
    while True:
        i = lower.find("<task>", start)
        if i == -1:
            break
        j = lower.find("</task>", i)
        if j == -1:
            blocks.append(text[i:])
            break
        blocks.append(text[i : j + len("</task>")])
        start = j + len("</task>")
    return blocks


def parse_tasks(text: str) -> list[Task]:
    tasks: list[Task] = []
    for raw in find_task_blocks(text):
        task_type = None
        m = re.search(r"<type>\s*([^<]+?)\s*</type>", raw, flags=re.IGNORECASE)
        if m:
            task_type = m.group(1).strip()

        if task_type:
            query = None
            mq = re.search(r"<query>\s*([\s\S]*?)\s*</query>", raw, flags=re.IGNORECASE)
            if mq:
                query = mq.group(1).strip()

            top_k = None
            mk = re.search(r"<top_k>\s*(\d+)\s*</top_k>", raw, flags=re.IGNORECASE)
            if mk:
                try:
                    top_k = int(mk.group(1))
                except ValueError:
                    top_k = None

            tasks.append(Task(task_type=task_type, raw=raw, query=query, top_k=top_k))
            continue

        inner_match = re.search(r"<task>\s*([\s\S]*?)\s*</task>", raw, flags=re.IGNORECASE)
        if not inner_match:
            inner_match = re.search(r"<task>\s*([\s\S]*)", raw, flags=re.IGNORECASE)
        if not inner_match:
            continue

        inner = inner_match.group(1).strip()
        try:
            data = json.loads(inner)
        except Exception:
            try:
                decoder = json.JSONDecoder()
                data, _ = decoder.raw_decode(inner)
            except Exception:
                data = None

        if data is not None and isinstance(data, (dict, list)):
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    name = (item.get("type") or item.get("name") or item.get("task_type") or "").strip()
                    if not name:
                        continue
                    query = item.get("query") or None
                    top_k = item.get("top_k") or item.get("k") or None
                    try:
                        top_k = int(top_k) if top_k is not None else None
                    except Exception:
                        top_k = None
                    tasks.append(Task(task_type=name, raw=raw, query=query, top_k=top_k))
            continue

        task_name = None
        if "knowledge_retrieval" in inner.lower() or "knowledge_retrieval.md" in inner.lower():
            task_name = "knowledge_retrieval"
        elif u'\u77e5\u8bc6\u68c0\u7d22' in inner:
            task_name = "knowledge_retrieval"

        query = None
        mq = re.search(r'(?:\u8f93\u5165)?\u67e5\u8be2\u8bcd\u4e3a[\u300c\u201c\u2018"\u2018]([\s\S]*?)[\u300d\u201d\u2019"\u2019]', inner)
        if mq:
            query = mq.group(1).strip()
        if not query:
            mq = re.search(r'\bquery\b\s*[:：]\s*([^\n\r]+)', inner, flags=re.IGNORECASE)
            if mq:
                query = mq.group(1).strip().strip('"\u201c\u201d\u2018\u2019')

        if task_name:
            tasks.append(Task(task_type=task_name, raw=raw, query=query, top_k=None))
        continue
    return tasks


def iter_index_md_paths(repo_dir: str) -> list[str]:
    index_path = os.path.join(repo_dir, "context", "index.md")
    if not os.path.exists(index_path):
        return []
    content = read_text_file(index_path)
    paths = []
    for p in re.findall(r"\(file:///(.+?)\)", content):
        p = p.replace("%20", " ")
        if p.endswith(".md") and os.path.exists(p):
            paths.append(p)
    seen = set()
    out = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def iter_md_files(repo_dir: str) -> list[str]:
    roots = [
        os.path.join(repo_dir, "context"),
        os.path.join(repo_dir, "skills"),
    ]
    md_files: list[str] = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if fn.lower().endswith(".md"):
                    md_files.append(os.path.join(dirpath, fn))
    return md_files


def score_text(haystack: str, query: str) -> int:
    q = query.strip()
    if not q:
        return 0
    tokens = [t for t in re.split(r"[\s,;，；]+", q) if t]
    if not tokens:
        tokens = [q]
    score = 0
    lower = haystack.lower()
    for t in tokens:
        tl = t.lower()
        if not tl:
            continue
        score += lower.count(tl) * max(1, min(5, len(tl)))
    return score


def extract_relevant_snippet(md_text: str, query: str, max_chars: int = 1800) -> str:
    lines = md_text.splitlines()
    if not lines:
        return ""

    tokens = [t for t in re.split(r"[\s,;，；]+", query.strip()) if t] or [query.strip()]
    match_line_idx = None
    for i, line in enumerate(lines):
        if any(t and t in line for t in tokens):
            match_line_idx = i
            break
    if match_line_idx is None:
        return ""

    header_idx = None
    header_level = None
    for j in range(match_line_idx, -1, -1):
        m = re.match(r"^(#{1,6})\s+", lines[j])
        if m:
            header_idx = j
            header_level = len(m.group(1))
            break

    if header_idx is None:
        start = max(0, match_line_idx - 10)
        end = min(len(lines), match_line_idx + 25)
        snippet = "\n".join(lines[start:end]).strip()
        return snippet[:max_chars]

    end = len(lines)
    for k in range(header_idx + 1, len(lines)):
        m = re.match(r"^(#{1,6})\s+", lines[k])
        if m and len(m.group(1)) <= (header_level or 6):
            end = k
            break

    snippet = "\n".join(lines[header_idx:end]).strip()
    return snippet[:max_chars]


def extract_images(snippet: str, source_path: str) -> list[dict]:
    seen = set()
    images = []
    for alt, path in re.findall(r"!\[(.*?)\]\((.*?)\)", snippet):
        key = (alt, path, source_path)
        if key in seen:
            continue
        seen.add(key)
        images.append({"alt": alt, "path": path, "source": source_path})
    return images


def knowledge_retrieval(_repo_dir: str, query: str, top_k: int = 3) -> dict:
    from skills.knowledge_retrieval.hybrid_search import retrieve
    return retrieve(query, top_k=top_k)


def format_knowledge_retrieval_result(result: dict) -> str:
    hit_text = (result.get("hit_text") or "").strip()
    images = result.get("images") or []
    out = []
    out.append("### 命中文本")
    out.append(hit_text if hit_text else "（未命中）")
    if images:
        out.append("")
        out.append("### 命中图片（可选）")
        for img in images:
            alt = (img.get("alt") or "").strip()
            path = (img.get("path") or "").strip()
            source = (img.get("source") or "").strip()
            out.append(f"- alt: {alt}")
            out.append(f"  path: {path}")
            out.append(f"  source: {source}")
    return "\n".join(out).strip()


def call_chat_completions_stream(api_key: str, payload: dict, ssl_context: ssl.SSLContext) -> tuple[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(
        ARK_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    assistant_content = []
    assistant_reasoning = []
    try:
        with urllib.request.urlopen(req, timeout=300, context=ssl_context) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text/event-stream" not in content_type and "application/json" in content_type:
                body = resp.read().decode("utf-8", errors="replace")
                print(body)
                return ("", "")

            saw_think = False
            for data in iter_sse_data_lines(resp):
                if data == "[DONE]":
                    if saw_think:
                        sys.stdout.write("\n</think>\n")
                    sys.stdout.flush()
                    break

                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue

                choices = event.get("choices") or []
                if not choices:
                    continue

                delta = (choices[0] or {}).get("delta") or {}

                reasoning = delta.get("reasoning_content")
                if reasoning:
                    assistant_reasoning.append(reasoning)
                    if not saw_think:
                        saw_think = True
                        sys.stdout.write("<think>\n")
                    sys.stdout.write(reasoning)
                    sys.stdout.flush()
                    continue

                content = delta.get("content")
                if content:
                    assistant_content.append(content)
                    if saw_think:
                        sys.stdout.write("\n</think>\n")
                        saw_think = False
                    sys.stdout.write(content)
                    sys.stdout.flush()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code} {e.reason}\n{body}", file=sys.stderr)
        raise

    return ("".join(assistant_content), "".join(assistant_reasoning))


def dispatch_skill(repo_dir: str, task: Task) -> str:
    skill_path = SKILL_REGISTRY.get(task.task_type)
    if not skill_path:
        return f"Unsupported task type: {task.task_type}"

    if task.task_type == "knowledge_retrieval":
        q = task.query or ""
        k = task.top_k or 3
        if DEBUG:
            print(f"[debug] executing knowledge_retrieval query={q!r} top_k={k}", file=sys.stderr)
        result = knowledge_retrieval(repo_dir, q, k)
        return format_knowledge_retrieval_result(result)

    full_path = os.path.join(repo_dir, skill_path)
    try:
        content = read_text_file(full_path)
    except Exception:
        return f"Failed to load skill file: {skill_path}"

    return (
        f"[Skill 已加载: {task.task_type}]\n"
        f"以下是该 Skill 的完整指令，你必须严格遵循这些步骤完成任务。"
        f"不可跳过任何必要环节，不可自行发挥：\n\n"
        f"{content}"
    )


def _run_agent_turn(
    api_key: str,
    payload: dict,
    ssl_context: ssl.SSLContext,
    messages: list[dict],
    repo_dir: str,
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

        result_text = dispatch_skill(repo_dir, task)

        sys.stdout.write("\n\n[task executed]\n")
        sys.stdout.flush()

        messages.append(
            {
                "role": "user",
                "content": (
                    "<task_result>\n"
                    f"<type>{task.task_type}</type>\n"
                    f"<result>\n{result_text}\n</result>\n"
                    "</task_result>"
                ),
            }
        )
        if DEBUG:
            print("[debug] task_result appended, will ask model to continue", file=sys.stderr)

    return task_calls, True


def main() -> int:
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        print("Missing env var ARK_API_KEY", file=sys.stderr)
        return 2

    repo_dir = os.path.dirname(os.path.abspath(__file__))
    agent_md_path = os.path.join(repo_dir, "agent.md")
    system_prompt = read_text_file(agent_md_path)
    tool_protocol = (
        "你需要通过 <task>...</task> 标签调用 Skill 来完成任务。"
        "<task> 内必须是 JSON 数组：[{\"name\":\"<skill_name>\",\"query\":\"...\",\"top_k\":3}]。"
        "\n可用 Skill：\n"
        "  - knowledge_retrieval: 检索知识库（必须提供 query）\n"
        "  - clarifying_questions: 反问用户补充信息\n"
        "  - product_feature_usage: 产品功能使用方法\n"
        "  - usage_scenarios: 产品功能使用案例\n"
        "  - scenario_solutions: 场景方案建议\n"
        "  - build_business_system: 搭建业务系统指南\n"
        "  - git_sync: 项目同步\n"
        "  - context_transformation: Context 转化与索引维护\n"
        "  - temporary_context_management: 临时内容记录\n"
        "\n收到 <task> 后，我会加载对应 Skill 文件的完整内容并注入上下文。"
        "你收到 <task_result> 后，必须严格按 Skill 文件中定义的执行步骤完成任务。"
        "如果你已经有足够信息可以直接回答用户，则无需输出 <task>。"
        "可以一次输出多个 <task>（数组中有多个元素），我会依次执行。"
        "请不要把 <task> 放进代码块里。"
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": tool_protocol},
    ]

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
                "model": "doubao-seed-2-0-code-preview-260215",
                "messages": messages,
                "stream": True,
                "thinking": {"type": "enabled"},
            }

            task_calls, should_continue = _run_agent_turn(
                api_key, payload, ssl_context, messages, repo_dir, task_calls, last_task_fingerprints
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
