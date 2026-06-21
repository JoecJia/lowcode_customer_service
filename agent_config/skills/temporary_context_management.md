# Skill: 临时 Context 管理 (Temporary Context Management)

## 描述
此技能用于记录日常产生的临时内容、灵感或业务细节。这些内容通常具有时效性，需要每天进行整理，并最终合并到永久知识库（Permanent Context）中。

## 输入参数
- `action` (string): 执行的操作，可选值：`record` (记录), `view` (查看), `process` (处理/整理)。
- `main_issue` (string): 当 `action` 为 `record` 时，记录的主要问题或核心内容。
- `needs_context` (boolean): 是否需要后续将其正式记录在永久 Context 中。
- `record_content` (string): 需要记录的具体细节内容（若是任务日志，则包含大模型回答、用户回答、步骤运行详情等）。
- `target_category` (string): 当 `action` 为 `process` 时，指定内容迁移到的永久 Context 类别（如 FAQ, Logic, Product Docs）。

## 执行逻辑
1. **记录 (record)**：
   - **动态建档**：根据当前日期生成或定位临时文件，路径为 `context/temporary/temp_notes_YYYYMMDD.md`。
   - **结构化记录**：在文件中按条记录日志，每条日志必须包含以下格式：
     - **时间戳**：[HH:mm:ss]
     - **主要问题/内容**：`{main_issue}`
     - **是否需入库**：`{needs_context ? "是" : "否"}`
     - **入库内容**：`{record_content}`
2. **查看 (view)**：
   - 列出 `context/temporary/` 目录下近期的所有日期文件。
   - 读取指定日期或今日文件中的未处理记录。
3. **处理 (process)**：
   - 提取标记为“需入库”的记录。
   - 根据 `target_category` 将内容改写并合并到对应的永久 Context 文件中。
   - 更新 `context/index.md`（如有必要）。
   - 处理完成后，在原临时记录中标记为“已处理”。

## 优势
- **即时记录**：防止灵感或重要业务细节遗失。
- **知识闭环**：通过每日处理机制，确保临时信息最终转化为系统永久知识。
- **减少碎片化**：集中管理临时信息，保持永久知识库的整洁和结构化。

## 使用示例
- 用户说：“记录一下，今天的客户反馈说导出按钮在手机上太小了。”
- Skill 动作：调用 `record` 操作，将内容存入 `temp_notes.md`。
- 用户说：“整理一下关于导出按钮的反馈，加到 FAQ 里。”
- Skill 动作：调用 `process` 操作，将内容迁移至 `context/faq/general_faq.md`。
