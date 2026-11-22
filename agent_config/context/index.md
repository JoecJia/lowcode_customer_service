# 知识库总索引 (Knowledge Base Index)

> 说明：下表路径均为**相对仓库根目录**的相对路径，禁止写入本机绝对路径。

## 目录映射
- **产品文档 (Product Docs)**
  - 路径: `agent_config/context/product_docs/`
  - 索引内容:
    - [产品介绍](agent_config/context/product_docs/product_intro.md): 超星低代码平台概览，包含表单、审批、仪表盘、信息查询、数据工厂、聚合表、业务流等核心引擎介绍。
    - [公式编辑使用指南](agent_config/context/product_docs/formula_guide.md): 包含公式编辑定义、使用流程、函数分类（数学、文本、日期、逻辑等）及注意事项。
    - [业务流程管理使用手册](agent_config/context/product_docs/business_process_management.md): 包含连通器管理、用户管理、组织架构管理、常见问题及视频演示案例。
    - [聚合表使用说明](agent_config/context/product_docs/aggregation_table.md): 包含进销存场景分析、名词解释、开通方式、创建步骤及操作指南。
    - [表单使用说明](agent_config/context/product_docs/form_usage_guide.md): 包含表单引擎简介、功能优势、创建方式、设计流程及高级设置。
    - [审批引擎使用手册](agent_config/context/product_docs/approval_engine_guide.md): 包含审批流程设计、节点配置、审批权限及常见问题处理。
    - [图表引擎使用说明](agent_config/context/product_docs/chart_engine_guide.md): 包含多维数据分析、各类统计图表（柱状图、饼图、折线图等）配置、数据源设置及布局管理。
    - [信息查询使用指南](agent_config/context/product_docs/info_query_guide.md): 包含从表单、审批和 Excel 中快速查询信息、多源数据匹配及查询结果展示。
    - [数据工厂使用指南](agent_config/context/product_docs/data_factory_guide.md): 包含数据加工处理工具、八大核心节点（横向连接、追加合并、分组汇总等）、数据同步及分析流程。
    - [办公产品学习资料汇总](agent_config/context/product_docs/learning_resources_summary.md): 包含各引擎使用说明、更新日志、答疑群信息及培训会议资料。
- **API & SDK 接口文档 (API & SDK)**
  - 路径: `agent_config/context/API&SDK/`
  - 索引内容:
    - [API & SDK 接口文档总览](agent_config/context/API&SDK/index.md): ShowDoc 导出的表单引擎 WebAPI（60 篇）、审批引擎 WebAPI（61 篇）、表单/审批 SDK（66 篇）三套文档的总入口，含项目导航与分类清单。
    - [接口链接清单](agent_config/context/API&SDK/接口链接.md): 187 个接口的「接口名称 → ShowDoc 在线地址 → 知识库文档路径」对照表，按项目与分类分组；检索接口文档时据此返回官方接口地址。
    - [表单引擎 webAPI 目录索引](agent_config/context/API&SDK/表单/_index.md): 逐页索引，覆盖表单应用、表单配置、表单数据增删改查、数据推送、页面地址、推送提醒、计划上线等接口。
    - [审批引擎 webAPI 目录索引](agent_config/context/API&SDK/审批/_index.md): 逐页索引，覆盖通用审批服务、数据检索/增删改、审批流程流转、审批应用与配置、流程查询、数据统计、审批助手等接口。
    - [表单/审批 SDK 目录索引](agent_config/context/API&SDK/SDK/_index.md): 逐页索引，含 v1.x（推荐）与 v0.x（旧版）两套的使用方式、FormsData/LogicSearchFilter 构造、表单/审批接口及 Response 属性说明。
    - [SDK 办公业务码 code 说明](agent_config/context/API&SDK/SDK/办公业务码code说明.md): 对接时使用的业务码 code 取值与含义。
    - [表单字段类型标识字典](agent_config/context/API&SDK/SDK/表单字段类型标识字典.md): 表单字段类型标识与对应取值，接口传参时用于识别字段类型。
    - [办公 SDK 版本更新说明](agent_config/context/API&SDK/SDK/办公SDK版本更新说明.md): SDK 版本演进、兼容性及各版本新增/变更接口。
    - [通用审批服务申请接口](<agent_config/context/API&SDK/审批/通用审批服务/通用审批服务申请接口.md>): 第三方发起通用审批的入参、流程节点与返回值说明。
    - [审批环节流程结构说明](<agent_config/context/API&SDK/审批/通用审批服务/审批环节流程结构说明.md>): 审批环节与流程节点的结构定义，对接审批接口前的前置知识。
    - [单条数据新增接口](<agent_config/context/API&SDK/表单/表单数据接口(增删改查)/单条数据新增接口.md>): 表单数据写入接口的参数构造与示例。
    - [SDK v1.x 使用方式](<agent_config/context/API&SDK/SDK/v1.x/使用方式.md>): v1.x SDK 的引入、初始化与调用流程。
    - [SDK v1.x 表单数据 FormsData 构造方式](<agent_config/context/API&SDK/SDK/v1.x/表单数据FormsData构造方式.md>): 表单数据对象构造规则，写入/编辑接口必读。
    - [SDK v1.x 检索条件 LogicSearchFilter 构造方式](<agent_config/context/API&SDK/SDK/v1.x/检索条件LogicSearchFilter构造方式.md>): 高级检索条件（且/或混合）的构造规则。
- **业务逻辑 (Logic)**
  - 路径: `agent_config/context/logic/`
  - 索引内容:
    - [业务逻辑](agent_config/context/logic/business_logic.md): 包含账号注册、激活、验证码、强密码、实名认证、管理员权限、编辑者权限、查看者权限。
- **业务系统搭建与咨询 (Business System & Consulting)**
  - 路径: `agent_config/skills/`
  - 索引内容:
    - [搭建业务系统指南](agent_config/skills/build_business_system.md): 包含系统名称定义、场景分析、模板推荐、流程设计、建设步骤。
    - [产品功能使用方法](agent_config/skills/product_feature_usage.md): 具体功能的操作路径、配置参数及注意事项。
    - [产品功能使用案例](agent_config/skills/usage_scenarios.md): 各模块的应用案例、适用场景、功能实现逻辑及关联推荐。
    - [场景方案建议](agent_config/skills/scenario_solutions.md): 根据用户痛点提供“产品组合”整体设计方案。
- **常见问题 (FAQ)**
  - 路径: `agent_config/context/faq/`
  - 索引内容:
    - [常见问题](agent_config/context/faq/general_faq.md): 包含忘记密码、重置密码、数据导出、Excel/CSV格式、AI填充准确度优化、汇总数据查看原始明细。
- **临时内容 (Temporary Context)**
  - 路径: `agent_config/context/temporary/`
  - 索引内容:
    - [临时笔记](agent_config/context/temporary/temp_notes.md): 存放每日产生的临时记录、待处理灵感及业务反馈。
- **Context 转化与索引管理 (Context Transformation)**
  - 路径: `agent_config/skills/context_transformation/`
  - 索引内容:
    - [Context 转化](agent_config/skills/context_transformation/context_transformation.md): 自动化将上传文件转为结构化 Context，处理图片/链接，维护索引。
- **信息补充与反问 (Clarifying Questions)**
  - 路径: `agent_config/skills/`
  - 索引内容:
    - [信息补充与反问](agent_config/skills/clarifying_questions.md): 用户信息不足时的反问机制，包含上下文总结、缺口识别及精准反问。

## 检索说明
1. 检索时先匹配“索引内容”中的关键词。
2. 根据匹配到的标题，跳转至对应的 Markdown 文件路径（相对仓库根目录）。
3. 仅提取与用户问题高度相关的段落返回给总调度智能体。
