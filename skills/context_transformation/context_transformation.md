# Skill: Context 转化与自动化索引 (Context Transformation & Auto-Indexing)

## 描述
该技能用于将用户上传的原始文件（如 .docx 文档、图片等）转化为结构化、层级分明的 Markdown Context，并自动维护 `context/index.md` 索引。它具备文档解析、图片提取、层级映射以及索引自动化维护的能力。

## 目录结构
- `docx_to_md.py`: 核心转换脚本，支持将 .docx 转为 .md 并提取图片。
- `context_transformation.md`: 技能描述与使用指南。

## 输入参数
- `file_path` (string): 待处理的原始文件路径（目前支持 .docx）。
- `target_directory` (string, optional): 存放转化后文件的目录，默认为 `context/product_docs/`。
- `assets_directory` (string, optional): 存放提取图片的目录，默认为 `context/assets/`。

## 执行逻辑

### 1. 文档解析与图片提取
使用 `docx_to_md.py` 脚本进行转换：
- **文本转换**：保留标题层级（H1-H6）、列表（1.、1、等）及段落。
- **图片提取**：自动从 docx 中提取所有图片，并存储在指定的 assets 目录下。
- **引用关联**：在生成的 Markdown 中自动插入图片的相对路径引用。

### 2. 自动化索引维护
- **位置建议**：分析内容，匹配 `context/index.md` 中的既有分支（如：产品文档、业务逻辑等）。
- **更新索引**：在 `context/index.md` 中添加新生成文档的条目，包含文件链接和内容摘要。

### 3. 源文件归档
- **自动移动**：转换成功后，若源文件位于 `documents_all/to_be_converted/` 目录下，脚本会自动将其移动至 `documents_all/have_been_converted/` 目录，实现流程闭环。

## 使用方法 (CLI)
可以使用 Python 脚本手动运行转换：
```bash
python3 skills/context_transformation/docx_to_md.py "input_file.docx" "output_file.md" --assets "../assets/folder_name"
```

## 自定义处理规则 (自我进化区)
- **列表识别**：已增强对中文序号（如 "1、"）的识别。
- **图片路径**：图片引用统一使用相对于 Markdown 文件的相对路径。
- **多级标题**：支持从 docx 样式中自动映射 H1-H6 标题。
