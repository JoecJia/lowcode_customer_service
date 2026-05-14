# Skill: 临时 Context 管理 (Temporary Context Management)

## 描述
此技能用于记录日常产生的临时内容、灵感或业务细节。这些内容通常具有时效性，需要每天进行整理，并最终合并到永久知识库（Permanent Context）中。

## 输入参数
- `action` (string): 执行的操作，可选值：`record` (记录), `view` (查看), `process` (处理/整理)。
- `content` (string): 当 `action` 为 `record` 时，需要记录的具体内容。
- `target_category` (string): 当 `action` 为 `process` 时，指定内容迁移到的永久 Context 类别（如 FAQ, Logic, Product Docs）。

## 执行逻辑
1. **记录 (record)**：
   - 将 `content` 附加到 `context/temporary/temp_notes.md` 的“记录区”下方。
   - 自动添加日期戳。
2. **查看 (view)**：
   - 读取 `context/temporary/temp_notes.md` 并展示当前所有未处理的记录。
3. **处理 (process)**：
   - 提取指定的临时内容。
   - 根据 `target_category` 将内容改写并合并到对应的永久 Context 文件中。
   - 更新 `context/index.md`（如有必要）。
   - 从 `context/temporary/temp_notes.md` 中删除已处理的内容。

## 优势
- **即时记录**：防止灵感或重要业务细节遗失。
- **知识闭环**：通过每日处理机制，确保临时信息最终转化为系统永久知识。
- **减少碎片化**：集中管理临时信息，保持永久知识库的整洁和结构化。

## 使用示例
- 用户说：“记录一下，今天的客户反馈说导出按钮在手机上太小了。”
- Skill 动作：调用 `record` 操作，将内容存入 `temp_notes.md`。
- 用户说：“整理一下关于导出按钮的反馈，加到 FAQ 里。”
- Skill 动作：调用 `process` 操作，将内容迁移至 `context/faq/general_faq.md`。
