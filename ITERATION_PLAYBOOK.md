# 迭代抓手（把“智能客服”当成可持续演进的产品）

本文件用于把当前仓库的“智能客服”迭代方式产品化、工程化：稳定可控地升级 Skills、知识库与主控规则，并用低成本回归防退化。

## 1. 把 Skills 当作 API 来管

### 1.1 稳定面与演进面
- 必须稳定（不轻易变更）
  - Skill 的触发条件边界、输入输出结构、失败/兜底行为
  - `knowledge_retrieval` 的“索引定位 → 命中片段提取”的检索路径
  - `temporary_context_management` 的“record → process → 更新 index”的闭环流程
  - 主控的兜底逻辑与死循环监控要求
- 允许演进（可迭代优化）
  - Skill 内部的提示词表述、输出文案的精炼与更清晰的结构化表达
  - 反问策略的命中率与问题设计（在不改变输入输出约束的前提下）
  - 知识库内容覆盖度与索引关键词完善

### 1.2 Skill 规范模板（建议约束点）
每个 Skill 都应明确并尽量保持稳定：
- 触发条件：用户问什么/提供什么信息时触发；哪些情况必须先反问
- 输入：参数列表与约束（必填/可选/格式）
- 输出：固定结构（例如“操作路径 → 关键设置 → 注意事项”）
- 边界：不做什么；遇到信息不足如何处理；与哪些 Skill 协作
- 失败处理：失败判据、如何降级、如何记录到临时区

参考主控规范：[agent.md](file:///Users/joec/Joec‘s%20code/P7_lowcode_customer_service/agent.md)

## 2. 建立“知识闭环”流水线

### 2.1 闭环目标
- 把对话中的新增知识、模糊点、失败案例，先沉淀到临时区，避免“只在聊天里解决”
- 定期把高价值内容入库到 FAQ/产品文档/方案文档，并更新索引，让后续能被 `knowledge_retrieval` 命中

### 2.2 流程（record → process → 更新 index）
- 临时记录（每天）
  - 触发：答不准/答不全/需要人工/用户提供了新资料/出现新规则
  - 动作：调用临时记录机制，将内容写入当日 `temp_notes_YYYYMMDD.md`
  - 参考 Skill：[temporary_context_management.md](file:///Users/joec/Joec‘s%20code/P7_lowcode_customer_service/skills/temporary_context_management.md)
- 入库处理（每周）
  - 从临时区挑选 Top 问题与典型失败案例，归类到：
    - 常见问题：`context/faq/`
    - 产品文档：`context/product_docs/`
    - 业务逻辑/方案：`context/logic/`
  - 同步补齐索引关键词与路径：`context/index.md`

索引位置：[index.md](file:///Users/joec/Joec‘s%20code/P7_lowcode_customer_service/context/index.md)

## 3. 用小规模“回归集”防退化

### 3.1 回归集的目的
每次改动（Skill 规则、检索策略、话术结构）都用一组固定问题回放，关注：
- 意图分类是否变差（是否更容易走错 Skill）
- 回答是否更长更绕（信息密度是否下降）
- 是否出现新幻觉/越权建议（例如编造功能、路径）
- 追问轮数是否异常上升（反问策略是否过度）

### 3.2 回归集组织方式（不新增仓库结构的前提下）
建议先用“表格+断言点”的方式组织，后续再工程化为脚本化回放。

推荐把回归集内容维护在本文件中（或临时区汇总后再搬运到本文件），格式如下：

| CaseID | 用户问题 | 期望意图分类 | 期望调用 Skill | 必须命中的知识文件（可选） | 通过标准 |
|---|---|---|---|---|---|
| R-001 | 我导出 Excel 时手机号是脱敏的，怎么处理？ | 产品功能使用 | product_feature_usage + knowledge_retrieval | context/product_docs/form_usage_guide.md | 给出“权限/脱敏设置”配置路径，含关键开关点 |
| R-002 | 填 A 表时如何自动带出 B 表手机号？ | 产品功能使用 | product_feature_usage + knowledge_retrieval | context/product_docs/form_usage_guide.md | 明确“数据联动”四步：联动表/条件/字段/排序 |

### 3.3 回归集的初始规模
- Top 30 高频问题：覆盖导出、权限、数据联动、流程审批、数据工厂等高频主题
- Top 10 典型失败问题：覆盖“信息不足需要反问”“分类易混淆”“曾经出现幻觉的点”

## 4. 建议的迭代节奏（低成本但稳定）

### 每天
- 对无法准确解决的问题执行临时记录（闭环入口）
- 优先保证“可追溯”：记录用户问法、已给出的答复、缺失信息、下一步建议

### 每周
- 处理临时记录入库（FAQ/产品文档/业务方案）
- 回补索引关键词（确保能被检索到）
- 复盘“反问”是否必要、是否太多，并优化反问路径

### 每两周或每月
- 信息架构整理：合并重复知识、清理过期内容、补索引
- 回看回归集指标：解决率、平均追问轮数、需要记录的比例

## 5. 发布检查清单（更新—自测—提交—同步）

### 5.1 更新前
- 明确本次改动范围：改了哪个 Skill/哪类问题/是否涉及索引与知识库
- 如果改动涉及检索：确认 `context/index.md` 有对应入口

### 5.2 自测（最小可用）
- 回放回归集中的相关 Case（至少覆盖本次改动涉及的 Top 问题）
- 检查回答是否遵循目标 Skill 的固定输出结构
- 若 `knowledge_retrieval` 命中片段包含图片引用，验证是否能把图片信息与文本一起输出

知识检索规范：[knowledge_retrieval.md](file:///Users/joec/Joec‘s%20code/P7_lowcode_customer_service/skills/knowledge_retrieval.md)

### 5.3 提交前
- 工作区干净：`git status` 无未提交文件（除预期修改外）
- 不引入大文件：确认 `documents_all/` 等目录不会进入提交
- 路径一致性：避免出现 Windows 风格路径，统一使用本仓库 macOS 绝对路径或相对路径

### 5.4 提交信息规范（建议）
- `feat:`：新增能力（例如“知识检索返回命中图片信息”）
- `fix:`：修复问题（例如“修复索引路径错误”）
- `docs:`：仅文档与知识库内容调整
- 提交信息包含“改了哪个 Skill/哪类问题”，便于回溯

### 5.5 同步（统一流程）
- 优先使用仓库内的同步 Skill 规范进行提交与同步：
  - [git_sync.md](file:///Users/joec/Joec‘s%20code/P7_lowcode_customer_service/skills/git_sync/git_sync.md)

