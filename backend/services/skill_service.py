import os

from config import REPO_DIR
from services.llm_service import Task, read_text_file
from services.mcp_service import mcp_manager

SKILL_REGISTRY = {
    "knowledge_retrieval": "../agent_config/skills/knowledge_retrieval/knowledge_retrieval.md",
    "clarifying_questions": "../agent_config/skills/clarifying_questions.md",
    "product_feature_usage": "../agent_config/skills/product_feature_usage.md",
    "usage_scenarios": "../agent_config/skills/usage_scenarios.md",
    "scenario_solutions": "../agent_config/skills/scenario_solutions.md",
    "build_business_system": "../agent_config/skills/build_business_system.md",
    "context_transformation": "../agent_config/skills/context_transformation/context_transformation.md",
    "temporary_context_management": "../agent_config/skills/temporary_context_management.md",
    "feedback_form_link": "../agent_config/skills/feedback_form_link.md",
}

TOOL_PROTOCOL = (
    "你需要通过 <task>...</task> 标签调用 Skill 来完成任务。"
    "<task> 内必须是 JSON 数组：[{\"name\":\"<skill_name>\",\"query\":\"...\",\"top_k\":3}]。"
    "\n可用 Skill：\n"
    "  - knowledge_retrieval: 检索知识库（必须提供 query）\n"
    "  - clarifying_questions: 反问用户补充信息\n"
    "  - product_feature_usage: 产品功能使用方法\n"
    "  - usage_scenarios: 产品功能使用案例\n"
    "  - scenario_solutions: 场景方案建议\n"
    "  - build_business_system: 搭建业务系统指南\n"
    "  - context_transformation: Context 转化与索引维护\n"
    "  - temporary_context_management: 临时内容记录\n"
    "  - feedback_form_link: 生成问题反馈表填写链接（自动预填对话总结）\n"
    "\n收到 <task> 后，我会加载对应 Skill 文件的完整内容并注入上下文。"
    "你收到 <task_result> 后，必须严格按 Skill 文件中定义的执行步骤完成任务。"
    "如果你已经有足够信息可以直接回答用户，则无需输出 <task>。"
    "可以一次输出多个 <task>（数组中有多个元素），我会依次执行。"
    "请不要把 <task> 放进代码块里。"
    "\n\n除上述 Skill 外，你还可以调用外部 MCP 工具（清单见下方 [可用 MCP 工具] 部分，若为空则没有可用的外部工具）。"
    "MCP 工具通过 <task> 调用，标签形式："
    "<task><type>工具名</type><arguments>{\"参数名\": 值}</arguments></task>，"
    "或 JSON 数组形式：[{\"name\":\"工具名\",\"arguments\":{\"参数名\": 值}}]。"
    "调用时必须根据工具的必填参数提供完整参数。"
)


def get_system_messages() -> list[dict]:
    agent_md_path = os.path.join(os.path.dirname(REPO_DIR), "agent_config", "agent.md")
    system_prompt = read_text_file(agent_md_path)
    # 动态注入 MCP 工具目录（未连接任何 Server 时为空串，不影响原有行为）
    catalog = mcp_manager.render_tool_catalog()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": TOOL_PROTOCOL + catalog},
    ]


async def dispatch_skill(repo_dir: str, task: Task) -> str:
    skill_path = SKILL_REGISTRY.get(task.task_type)
    if skill_path:
        if task.task_type == "knowledge_retrieval":
            from services.search_service import knowledge_retrieval, format_knowledge_retrieval_result
            q = task.query or ""
            k = task.top_k or 3
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

    # 未命中内置 skill → 尝试 MCP 外部工具（命名含 server 前缀，天然隔离）
    if mcp_manager.find_tool(task.task_type):
        return await mcp_manager.call_tool(task.task_type, task.arguments or {})

    return f"Unsupported task type: {task.task_type}"


def format_task_result(task_type: str, result_text: str) -> dict:
    return {
        "role": "user",
        "content": (
            "<task_result>\n"
            f"<type>{task_type}</type>\n"
            f"<result>\n{result_text}\n</result>\n"
            "</task_result>"
        ),
    }
