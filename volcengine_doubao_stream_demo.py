import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


ARK_CHAT_COMPLETIONS_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

MAX_AGENT_TURNS = 6
MAX_TASK_CALLS = 10

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
            continue

        inner = inner_match.group(1).strip()
        try:
            data = json.loads(inner)
        except Exception:
            task_name = None
            if "knowledge_retrieval" in inner.lower() or "knowledge_retrieval.md" in inner.lower():
                task_name = "knowledge_retrieval"
            elif "知识检索" in inner:
                task_name = "knowledge_retrieval"

            query = None
            mq = re.search(r"(?:输入)?查询词为[「“\"']([\s\S]*?)[」”\"']", inner)
            if mq:
                query = mq.group(1).strip()
            if not query:
                mq = re.search(r"\bquery\b\s*[:：]\s*([^\n\r]+)", inner, flags=re.IGNORECASE)
                if mq:
                    query = mq.group(1).strip().strip("\"'“”")

            if task_name:
                tasks.append(Task(task_type=task_name, raw=raw, query=query, top_k=None))
            continue

        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            continue

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


def knowledge_retrieval(repo_dir: str, query: str, top_k: int = 3) -> dict:
    if not query.strip():
        return {"hit_text": "", "images": []}

    candidates = iter_index_md_paths(repo_dir)
    if not candidates:
        candidates = iter_md_files(repo_dir)

    scored: list[tuple[int, str]] = []
    for p in candidates:
        try:
            text = read_text_file(p)
        except Exception:
            continue
        s = score_text(text, query) + score_text(os.path.basename(p), query)
        if s > 0:
            scored.append((s, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [p for _, p in scored[: max(1, top_k)]]

    hit_sections: list[str] = []
    images: list[dict] = []
    for p in picked:
        try:
            text = read_text_file(p)
        except Exception:
            continue
        snippet = extract_relevant_snippet(text, query)
        if not snippet:
            continue
        hit_sections.append(f"[source] {p}\n{snippet}")
        images.extend(extract_images(snippet, p))

    hit_text = "\n\n---\n\n".join(hit_sections).strip()
    return {"hit_text": hit_text, "images": images}


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


def main() -> int:
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        print("Missing env var ARK_API_KEY", file=sys.stderr)
        return 2

    repo_dir = os.path.dirname(os.path.abspath(__file__))
    agent_md_path = os.path.join(repo_dir, "agent.md")
    system_prompt = read_text_file(agent_md_path)
    tool_protocol = (
        "当且仅当你需要我在本地执行任务时，输出 <task>...</task>。"
        "<task> 内必须是可被 json.loads 解析的 JSON（不要输出自然语言，不要加额外文本）。"
        "JSON 结构为数组：[{\"name\":\"knowledge_retrieval\",\"query\":\"...\",\"top_k\":3}]。"
        "我会把执行结果作为下一条 user 消息返回，格式为 <task_result>...</task_result>。"
        "收到 <task_result> 后，请继续完成对用户问题的最终回答。"
        "如果信息足够，请不要再次输出 <task>。"
        "请不要把 <task> 放进代码块里。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": tool_protocol},
        {"role": "user", "content": "数据联动是什么？"},
    ]

    ssl_context = build_ssl_context()
    task_calls = 0
    last_task_fingerprints: list[str] = []

    for _ in range(MAX_AGENT_TURNS):
        payload = {
            "model": "doubao-seed-2-0-code-preview-260215",
            "messages": messages,
            "stream": True,
            "thinking": {"type": "enabled"},
        }

        try:
            assistant_content, assistant_reasoning = call_chat_completions_stream(api_key, payload, ssl_context)
        except Exception as e:
            print(f"Request failed: {e}", file=sys.stderr)
            return 1

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
            return 0

        for task in tasks:
            task_calls += 1
            if task_calls > MAX_TASK_CALLS:
                print("\n[ABORT] Too many task calls, stop to avoid loop.\n", file=sys.stderr)
                return 3

            fingerprint = f"{task.task_type}|{task.query}|{task.top_k}"
            last_task_fingerprints.append(fingerprint)
            if len(last_task_fingerprints) >= 4 and len(set(last_task_fingerprints[-3:])) == 1:
                print("\n[ABORT] Repeated same task 3 times, stop to avoid loop.\n", file=sys.stderr)
                return 3

            if task.task_type != "knowledge_retrieval":
                result_text = f"Unsupported task type: {task.task_type}"
            else:
                q = task.query or ""
                k = task.top_k or 3
                if DEBUG:
                    print(f"[debug] executing knowledge_retrieval query={q!r} top_k={k}", file=sys.stderr)
                result = knowledge_retrieval(repo_dir, q, k)
                result_text = format_knowledge_retrieval_result(result)

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

    print("\n[ABORT] Reached max agent turns.\n", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
