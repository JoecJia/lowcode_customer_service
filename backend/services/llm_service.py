import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Generator

from config import ARK_CHAT_COMPLETIONS_URL, DEBUG


def _extract_api_error(body: str) -> str:
    """从 API 返回的 JSON 错误体中提取可读的错误信息。"""
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return body
    if isinstance(data, dict):
        err = data.get("error") or {}
        if isinstance(err, dict):
            msg = err.get("message") or err.get("code") or json.dumps(err, ensure_ascii=False)
            return str(msg)
        return str(err)
    return body


@dataclass(frozen=True)
class Task:
    task_type: str
    raw: str
    query: str | None = None
    top_k: int | None = None
    arguments: dict | None = None


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
        yield line[len("data:"):].strip()


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
        blocks.append(text[i: j + len("</task>")])
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

            arguments = None
            ma = re.search(r"<arguments>\s*([\s\S]*?)\s*</arguments>", raw, flags=re.IGNORECASE)
            if ma:
                try:
                    parsed_args = json.loads(ma.group(1).strip())
                    if isinstance(parsed_args, dict):
                        arguments = parsed_args
                except Exception:
                    arguments = None

            tasks.append(Task(task_type=task_type, raw=raw, query=query, top_k=top_k, arguments=arguments))
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
                    arguments = item.get("arguments")
                    if not isinstance(arguments, dict):
                        arguments = None
                    tasks.append(Task(task_type=name, raw=raw, query=query, top_k=top_k, arguments=arguments))
            continue

        task_name = None
        if "knowledge_retrieval" in inner.lower() or "knowledge_retrieval.md" in inner.lower():
            task_name = "knowledge_retrieval"
        elif "\u77e5\u8bc6\u68c0\u7d22" in inner:
            task_name = "knowledge_retrieval"

        query = None
        mq = re.search(
            r"(?:\u8f93\u5165)?\u67e5\u8be2\u8bcd\u4e3a"
            r'[\u300c\u201c\u2018"\u2018]([\s\S]*?)[\u300d\u201d\u2019"\u2019]',
            inner,
        )
        if mq:
            query = mq.group(1).strip()
        if not query:
            mq = re.search(r"\bquery\b\s*[:：]\s*([^\n\r]+)", inner, flags=re.IGNORECASE)
            if mq:
                query = mq.group(1).strip().strip('"\u201c\u201d\u2018\u2019')

        if task_name:
            tasks.append(Task(task_type=task_name, raw=raw, query=query, top_k=None))
        continue
    return tasks


def stream_chat_completions(
    api_key: str,
    payload: dict,
    ssl_context: ssl.SSLContext,
) -> Generator[tuple[str, str], None, None]:
    """调用火山引擎 Chat Completions API，返回 (delta_type, text) 的流式生成器。

    对 502/503/504 等临时性服务端错误自动重试，最多 3 次，间隔递增。
    """
    RETRIABLE_STATUSES = {502, 503, 504}
    MAX_RETRIES = 3

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(
            ARK_CHAT_COMPLETIONS_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=300, context=ssl_context) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "text/event-stream" not in content_type and "application/json" in content_type:
                    body = resp.read().decode("utf-8", errors="replace")
                    yield ("error", f"API 错误: {_extract_api_error(body)}")
                    return

                for data in iter_sse_data_lines(resp):
                    if data == "[DONE]":
                        return

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
                        yield ("reasoning", reasoning)
                        continue

                    content = delta.get("content")
                    if content:
                        yield ("content", content)
                return  # 正常结束，不再重试

        except urllib.error.HTTPError as e:
            last_error = e
            if e.code in RETRIABLE_STATUSES and attempt < MAX_RETRIES:
                wait = 2 ** attempt  # 1s, 2s, 4s
                if DEBUG:
                    print(f"[llm] HTTP {e.code}，第 {attempt + 1} 次重试，等待 {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            body = e.read().decode("utf-8", errors="replace")
            yield ("error", f"HTTP {e.code}: {_extract_api_error(body)}")
            return

        except urllib.error.URLError as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                if DEBUG:
                    print(f"[llm] URLError: {e.reason}，第 {attempt + 1} 次重试，等待 {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            yield ("error", f"网络连接失败（已重试 {MAX_RETRIES} 次）: {e.reason}")
            return

    # 所有重试耗尽
    if last_error is not None:
        body = getattr(last_error, 'read', lambda: b'')()
        body_str = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else ""
        yield ("error", f"服务暂时不可用（已重试 {MAX_RETRIES} 次）\n{_extract_api_error(body_str)}")


def _safe_write(text: str, file) -> None:
    """写入 stdout，忽略控制台编码不支持的字符（如 emoji）。"""
    try:
        file.write(text)
    except UnicodeEncodeError:
        file.write(text.encode(file.encoding or "utf-8", errors="replace").decode(file.encoding or "utf-8"))


def call_chat_completions_stream(
    api_key: str,
    payload: dict,
    ssl_context: ssl.SSLContext,
) -> tuple[str, str]:
    assistant_content: list[str] = []
    assistant_reasoning: list[str] = []
    saw_think = False

    for delta_type, text in stream_chat_completions(api_key, payload, ssl_context):
        if delta_type == "reasoning":
            assistant_reasoning.append(text)
            if not saw_think:
                saw_think = True
                _safe_write("<think>\n", sys.stdout)
            _safe_write(text, sys.stdout)
            sys.stdout.flush()
        elif delta_type == "content":
            assistant_content.append(text)
            if saw_think:
                _safe_write("\n</think>\n", sys.stdout)
                saw_think = False
            _safe_write(text, sys.stdout)
            sys.stdout.flush()
        elif delta_type == "error":
            print(text, file=sys.stderr)
            raise RuntimeError(text)

    if saw_think:
        _safe_write("\n</think>\n", sys.stdout)
        sys.stdout.flush()

    return ("".join(assistant_content), "".join(assistant_reasoning))


def format_assistant_message(content: str, reasoning: str | None = None) -> dict:
    msg: dict = {"role": "assistant", "content": content}
    if reasoning:
        msg["reasoning_content"] = reasoning
    return msg
