# Skill: Context 转化与自动化索引 (Context Transformation & Auto-Indexing)

## 描述
该技能用于将用户上传的原始文件（如 .docx 文档、图片等）转化为结构化、层级分明的 Markdown Context，并自动维护 `context/index.md` 索引。它具备文档解析、图片提取、图片压缩、层级映射以及索引自动化维护的能力。

**推荐流程**：使用 `transform_document.py` 一键完成 docx → md 转化 + 图片压缩发布。

## 目录结构
- `transform_document.py`: **文档转化流水线**（推荐入口），一键完成 docx→md + 图片暂存→压缩→发布到 `context/assets/`。
- `docx_to_md.py`: 核心转换脚本，支持将 .docx 转为 .md 并提取图片。也支持 HTML 格式的 .doc 文件。
- `compress_assets.py`: 图片批量压缩脚本，支持原地模式（`--dry-run`/`--rollback`）和 Pipeline 模式（`--source`/`--target`）。
- `extracted_assets/`: **临时暂存区**，存放文档解析时提取的原始图片（流水线完成后自动清理）。
- `vectorizer.py`: 向量化引擎，提供 MD 文档分块、Embedding 向量化、FAISS 索引管理与增量更新。
- `build_initial_index.py`: 一键构建全量向量索引的入口脚本。
- `update_index.py`: 向量索引维护 CLI 统一入口（status / update / rebuild）。
- `context_transformation.md`: 技能描述与使用指南。

## 推荐工作流：文档转化流水线 (Transform Pipeline)

### 流程概述
```
.docx 文件 
  → [Step 1] 解析文档，提取原始图片到 extracted_assets/<doc_name>/ (暂存区)
  → [Step 2] 生成 .md 文件，图片引用指向暂存区
  → [Step 3] 压缩暂存区图片 → context/assets/<category>/ (最终位置)
  → [Step 4] 重写 .md 中的图片引用 → context/assets/<category>/
  → [Step 5] 增量更新向量索引（调用 update_index.py update）
  → 清理暂存区
```

### 使用方法
```bash
# 一键转化（推荐）
python3 agent_config/skills/context_transformation/transform_document.py \
    "path/to/document.docx" \
    --output context/product_docs/my_doc.md \
    --category my_category

# 跳过索引更新（批量导入时先跳过，最后整体重建）
python3 agent_config/skills/context_transformation/transform_document.py \
    "path/to/document.docx" --skip-index

# 简化版（自动推断输出路径和分类名）
python3 agent_config/skills/context_transformation/transform_document.py "path/to/document.docx"
```

### 单独使用子步骤（高级）

```bash
# 仅转换 docx → md（手动指定 assets 路径）
python3 agent_config/skills/context_transformation/docx_to_md.py \
    "input.docx" "output.md" --assets "../assets/folder_name"

# 仅压缩图片（Pipeline 模式：source → target）
python3 agent_config/skills/context_transformation/compress_assets.py \
    --source extracted_assets/doc_name --target context/assets/doc_name
```

## 执行逻辑

### 1. 文档解析与图片提取
使用 `docx_to_md.py` 或 `transform_document.py` 流水线进行转换：
- **文本转换**：保留标题层级（H1-H6）、列表（1.、1、等）及段落。
- **图片提取**：自动从 docx 中提取所有图片，先放入 `extracted_assets/` 暂存区。
- **引用关联**：在生成的 Markdown 中自动插入图片的相对路径引用。

### 2. 图片压缩与发布
- 暂存区的原始图片经过 FASTOCTREE 量化压缩后，复制到 `context/assets/<category>/`。
- 压缩后的 .md 文件最终引用 `context/assets/` 中的路径。

### 3. 自动化索引维护
- **位置建议**：分析内容，匹配 `context/index.md` 中的既有分支（如：产品文档、业务逻辑等）。
- **更新索引**：在 `context/index.md` 中添加新生成文档的条目，包含文件链接和内容摘要。

### 4. 源文件归档
- **自动移动**：转换成功后，若源文件位于 `documents_all/to_be_converted/` 目录下，脚本会自动将其移动至 `documents_all/have_been_converted/` 目录，实现流程闭环。

## 自定义处理规则 (自我进化区)
- **列表识别**：已增强对中文序号（如 "1、"）的识别。
- **图片路径**：图片引用统一使用相对于 Markdown 文件的相对路径。
- **多级标题**：支持从 docx 样式中自动映射 H1-H6 标题。

---

## 图片压缩 (Image Compression)

### 概述
对 `agent_config/context/assets/` 下的 PNG 和 GIF 图片进行原地有损压缩，大幅减小体积（通常节省 90%+）。压缩前会自动备份原始图片到 `docs/convert_docs/assets_converts/`。

### 压缩策略
- **PNG**：若 RGBA 且 Alpha 完全不通透 → 转 RGB → FASTOCTREE 256色量化 → 保存。否则直接量化（保留透明度）。
- **GIF**：FASTOCTREE 128色量化 → save_all + optimize。

### 使用方法
```bash
# 预览压缩效果（不修改文件）
python3 agent_config/skills/context_transformation/compress_assets.py --dry-run

# 执行压缩（原地覆盖）
python3 agent_config/skills/context_transformation/compress_assets.py

# 从备份恢复原始文件
python3 agent_config/skills/context_transformation/compress_assets.py --rollback
```

### 触发场景
- 用户要求压缩 knowledge base 中的图片
- 新导入的文档包含大体积截图
- 部署前对 assets 目录做体积优化

---

## 向量化索引维护 (Vector Index Maintenance)

### 概述
为支持混合式检索（BM25 + 向量语义检索），本模块提供 MD 文档的向量化能力。使用 `BAAI/bge-small-zh-v1.5` 作为 Embedding 模型，FAISS 作为向量索引引擎。

### 索引产物
构建完成后，索引文件存储在 `context/.faiss/` 目录下（该目录已加入 `.gitignore`）：
- `index.faiss`：FAISS 向量索引文件
- `chunk_meta.json`：每个 chunk 的元信息（来源文件、标题链、文本内容、图片引用）

### 核心能力

#### 文档分块 (Chunking)
- 按 Markdown `##` 标题切分，保留完整的标题层级链（如：`公式编辑使用指南 > 一、公式编辑概述`）
- 每块最大 500 字符，超出部分按段落进一步切分
- 相邻块之间保留 50 字符重叠，防止信息断裂
- 自动提取块内图片引用（`![alt](path)`）

#### Embedding 向量化
- 模型：`BAAI/bge-small-zh-v1.5`（512 维），本地运行
- 文档编码：直接编码文本
- 查询编码：自动添加 BGE 推荐前缀 `为这个句子生成表示以用于检索相关文章：`
- 向量归一化：使用 L2 归一化，FAISS 内积等价于余弦相似度

### 使用方法

#### CLI 统一入口：update_index.py
`update_index.py` 是向量索引维护的 CLI 统一入口，供 Agent 通过命令行调用：

```bash
# 查看索引状态
python3 agent_config/skills/context_transformation/update_index.py status

# 增量更新单个文件（Agent 编辑文档后调用）
python3 agent_config/skills/context_transformation/update_index.py update context/faq/general_faq.md

# 全量重建索引（知识库大规模变更后）
python3 agent_config/skills/context_transformation/update_index.py rebuild
```

#### 初始全量索引构建
```bash
python3 agent_config/skills/context_transformation/build_initial_index.py
```
首次部署或知识库大规模变更后运行，扫描 `context/` 和 `skills/` 下所有 `.md` 文件并构建索引。

#### 代码级调用
```python
from agent_config.skills.context_transformation.vectorizer import update_document
update_document("context/faq/general_faq.md")
```
该函数会自动：
1. 移除该文件的旧 chunks 和对应向量
2. 重新分块 + 向量化
3. 追加到 FAISS 索引
4. 更新 chunk_meta.json

### 与 Agent 对话的联动
当管理员通过 agent 编辑了知识库文件后，agent 必须调用 `update_index.py` 确保向量索引与文件内容保持同步。流程示例：

```
管理员: "帮我把 FAQ 里数据导出的答案更新一下"
   → Agent 检索并编辑 context/faq/general_faq.md
   → Agent 执行: python3 agent_config/skills/context_transformation/update_index.py update context/faq/general_faq.md
   → 向量索引增量更新完成，后续检索可命中新内容
```
