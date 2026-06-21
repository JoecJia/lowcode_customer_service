"""Agent 配置文件服务"""

import os


def _get_agent_config_root() -> str:
    project_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(project_root, "agent_config")


def get_file_tree() -> list[dict]:
    """返回 agent_config/ 目录的完整树形结构"""
    root_dir = _get_agent_config_root()

    def walk(path: str, rel_path: str) -> list[dict]:
        nodes = []
        try:
            entries = sorted(os.listdir(path))
        except OSError:
            return nodes

        for name in entries:
            full = os.path.join(path, name)
            node_rel = os.path.join(rel_path, name) if rel_path else name

            if name.startswith('.') or name == '__pycache__':
                continue

            if os.path.isdir(full):
                children = walk(full, node_rel)
                nodes.append({
                    "name": name,
                    "type": "folder",
                    "path": node_rel,
                    "children": children,
                })
            else:
                ext = os.path.splitext(name)[1].lower()
                node = {
                    "name": name,
                    "type": "file",
                    "ext": ext,
                    "path": node_rel,
                }
                if ext != ".md":
                    node["previewable"] = False
                nodes.append(node)

        return nodes

    return walk(root_dir, "")


def get_file_content(file_path: str) -> str | None:
    """读取指定文件的完整内容，仅允许 agent_config/ 下的 .md 文件"""
    root_dir = _get_agent_config_root()
    full_path = os.path.normpath(os.path.join(root_dir, file_path))

    # 安全校验：路径必须在 agent_config/ 下
    if not full_path.startswith(os.path.normpath(root_dir) + os.sep) and full_path != os.path.normpath(root_dir):
        return None

    if not os.path.isfile(full_path):
        return None

    if not full_path.lower().endswith(".md"):
        return None

    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()
