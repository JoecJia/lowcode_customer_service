# 新增 / 修改 Skill 的方法

## 概述

本项目的 Skill 调度机制基于「代码读取 Skill 文件 → 注入上下文」模式。大模型通过 `<task>` 标签声明要调用的 Skill，Python 代码读取对应的 `.md` 文件内容注入到对话上下文中。

## 新增一个 Skill

只需三步：

### 步骤 1：编写 Skill 文件

在 `skills/` 目录下创建 `.md` 文件：

```
skills/
├── your_new_skill.md          # 简单 Skill（单文件）
│
└── your_new_skill/            # 复杂 Skill（含脚本，放在子目录中）
    ├── your_new_skill.md
    └── helper.py
```

Skill 文件内容需包含：
- **目标**：该 Skill 负责解决什么问题
- **执行步骤**：分步骤的操作指南，大模型将严格遵循
- **输出规范**：期望的输出格式

参考现有 Skill 文件如 `skills/clarifying_questions.md` 作为模板。

### 步骤 2：注册到 SKILL_REGISTRY

打开 `volcengine_doubao_stream_demo.py`，找到 `SKILL_REGISTRY` 字典（约第 19 行），添加一行：

```python
SKILL_REGISTRY = {
    # ... 已有条目 ...
    "your_new_skill": "skills/your_new_skill.md",  # 或 "skills/your_new_skill/your_new_skill.md"
}
```

- **Key**：`task_type` 名称，即大模型在 `<task>` 中使用的 `name` 字段值
- **Value**：Skill 文件相对于项目根目录的路径

### 步骤 3：在 tool_protocol 中列出

找到 `tool_protocol` 变量（约第 476 行），在「可用 Skill」列表中添加一行说明：

```python
tool_protocol = (
    # ... 已有内容 ...
    "\n可用 Skill：\n"
    "  - knowledge_retrieval: 检索知识库（必须提供 query）\n"
    # ... 已有条目 ...
    "  - your_new_skill: 你的 Skill 的简短描述\n"   # ← 添加这行
    # ...
)
```

描述应简洁明了，让大模型知道何时该调用此 Skill。

---

## 修改已有 Skill

### 修改 Skill 内容

直接编辑 `skills/` 下对应的 `.md` 文件即可，**无需修改任何 Python 代码**。

### 修改 Skill 名称

1. 重命名 Skill 文件
2. 更新 `SKILL_REGISTRY` 中的 key 和路径
3. 更新 `tool_protocol` 中的名称和描述

### 删除 Skill

1. 从 `SKILL_REGISTRY` 中移除对应条目
2. 从 `tool_protocol` 列表中移除对应行
3. （可选）删除 Skill 文件

---

## 特殊情况：需要自定义 Python 代码的 Skill

大多数 Skill 只需 `.md` 文件，`dispatch_skill()` 函数会自动读取文件内容并注入上下文。

如果 Skill 需要执行 Python 代码（如 `knowledge_retrieval` 需要调用混合搜索引擎），则需要在 `dispatch_skill()` 函数中增加分支：

```python
def dispatch_skill(repo_dir: str, task: Task) -> str:
    # ... 已有逻辑 ...

    if task.task_type == "your_new_skill":
        # 自定义 Python 逻辑
        result = your_custom_function(...)
        return format_result(result)

    # ... 通用文件加载逻辑 ...
```

---

## 目录结构约定

```
skills/
├── how_to_add_modify_skill.md       # 本文档
├── clarifying_questions.md           # 简单 Skill（单文件）
├── build_business_system.md          # 简单 Skill（单文件）
├── product_feature_usage.md          # 简单 Skill（单文件）
├── scenario_solutions.md             # 简单 Skill（单文件）
├── temporary_context_management.md   # 简单 Skill（单文件）
├── usage_scenarios.md                # 简单 Skill（单文件）
├── context_transformation/           # 复杂 Skill（含 Python 脚本）
│   ├── context_transformation.md
│   ├── vectorizer.py
│   ├── build_initial_index.py
│   └── update_index.py
├── git_sync/                         # 复杂 Skill（含脚本）
│   ├── git_sync.md
│   ├── sync_project.sh
│   └── sync_project.ps1
└── knowledge_retrieval/              # 复杂 Skill（含自定义代码分支）
    ├── knowledge_retrieval.md
    └── hybrid_search.py
```
