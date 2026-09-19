# 超星低代码智能客服 (Chaoxing Low-code Intelligent Customer Service)

基于 AI Agent 的智能客服平台，为「超星低代码」产品提供 7×24 自动技术支持。采用意图分类 + 多技能调度的 Agent 架构，结合向量检索与 LLM 流式对话，精准解答用户在表单、审批、数据工厂、图表引擎等模块的使用疑问。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Element Plus + Vite |
| 后端 | FastAPI + Uvicorn (Python 异步) |
| 数据库 | SQLite |
| 鉴权 | 超星 Passport Cookie 免登（VC3 验签）+ 本地 JWT (HS256, 1 天) |
| AI 大模型 | 豆包 Doubao-Seed-2.0-pro (火山引擎 Ark) |
| 向量检索 | FAISS + BM25 (jieba 分词) |
| Embedding | BAAI/bge-small-zh-v1.5 (512 维) |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Windows / macOS

### 1. 环境变量

项目根目录创建 `.env` 文件：

```env
ARK_API_KEY=your_volcengine_api_key
# 可选
SESSION_TTL_SECONDS=1800
DB_PATH=backend/data/app.db
JWT_SECRET=your_secret_key   # 生产环境务必替换为随机串
DEBUG=1

# 超星 Passport 登录（详见下方「登录说明」）
PASSPORT_BASE_URL=https://passport2-api.chaoxing.com/
PASSPORT_LOGIN_URL=https://passport2.chaoxing.com/login
PASSPORT_APP_ID=...
PASSPORT_APP_KEY=...            # 生产环境签名私钥
PASSPORT_APP_KEY_DEBUG=...      # 开发环境（VPN / 办公区 IP）签名私钥
PASSPORT_KEY_MODE=prod          # prod | debug
PASSPORT_API_USERINFO_KEY=...
PASSPORT_VC3_AES_KEY=...
PASSPORT_MD5_KEY=...
PASSPORT_SIMULATE_MD5_KEY=...
PASSPORT_FORWARD_CLIENT_INFO=true
APP_ORIGINS=https://service.cxlowcode.com
```

### 2. 手动启动

```bash
# 后端
pip install -r backend/requirements.txt
python backend/main.py          # → http://localhost:8000

# 前端
cd frontend && npm install && npm run dev   # → http://localhost:5173
```

开发模式下，前端 Vite 代理自动将 `/api`、`/health`、`/assets` 转发到后端 `:8000`。

### 3. 生产部署

```bash
cd frontend && npm run build     # 输出到 frontend/dist/
python backend/main.py           # 后端托管前端静态文件 → http://localhost:8000
```

### 4. 登录说明（超星 Passport 免登）

本系统不再提供自建账号密码登录，统一使用超星 passport 登录态：

1. **前置条件**：浏览器需已登录超星，且 passport Cookie 的 `Domain` 覆盖部署域名
   （生产为 `https://service.cxlowcode.com`，要求 Cookie 域为 `.cxlowcode.com`）。
2. **访问系统**：已登录超星时自动进入对话页，无需任何输入；未登录时点击「使用超星账号登录」跳转超星登录页（`?refer=` 回跳本站）。
3. **调试自检**：`python debug/passport_selfcheck.py` 可实测接口域名、签名私钥与 Cookie 验签；
   带上真实 Cookie 可验证整条验签链路：`python debug/passport_selfcheck.py --cookie "UID=..; fid=..; vc3=..; _d=.."`。
4. **首个管理员**：用超星账号登录一次后执行
   `UPDATE users SET can_admin = 1 WHERE uid = '<你的uid>';`（库文件 `backend/data/app.db`）。
5. **本地联调**：把 `service.cxlowcode.com` 指向本地（`C:\Windows\System32\drivers\etc\hosts` 加
   `127.0.0.1 service.cxlowcode.com`，再 `ipconfig /flushdns`）。Cookie 按域名匹配、忽略端口，
   因此 `:5173` 同样生效；若 passport Cookie 带 `Secure` 标记，本地需启用 HTTPS。
6. **签名私钥**：`PASSPORT_KEY_MODE=debug` 用于办公区 / VPN 环境，公网生产环境必须为 `prod`，
   否则 passport 会返回「signature 校验未通过，办公区 ip、VPN ip 请使用 debugKey」。

## 功能模块

### 客服对话页
- SSE 流式 AI 对话，支持 Markdown 实时渲染
- 思考过程透明展示（推理链 + Task 调度可视化）
- 多轮对话上下文记忆
- 会话管理（新建/切换/删除/重命名）
- 对话反馈（满意/不满意）

### 管理员后台
- 账号管理（创建/密码重置/权限变更）
- Agent 配置查看
- 用户反馈管理与处理

### 用户系统
- 超星 Passport Cookie 免登：与 passport 同域，浏览器自动携带 `UID` / `fid` / `vc3` / `_d`
- VC3 验签（MD5 尾校验 + `SHA256withRSA`，正式 → 模拟两轮）后签发本地 JWT（有效期 1 天）
- 未登录时引导跳转超星登录页（`?refer=` 回跳本站）
- 退出登录：只清本地登录态并写入标志位，刷新不会被自动登录回来

## AI Agent 架构

Agent 定义在 `agent_config/agent.md`，工作流如下：

```
用户输入 → 意图预检与反问 → 意图分类 → 任务规划 → 多技能调度 → 最终答复
```

### 技能 (Skills)

| 技能 | 说明 |
|---|---|
| `knowledge_retrieval` | BM25 + FAISS 混合检索，返回命中文本与图片 |
| `product_feature_usage` | 功能操作路径与配置参数 |
| `usage_scenarios` | 功能使用案例与场景 |
| `scenario_solutions` | 产品组合方案建议 |
| `build_business_system` | 业务系统搭建指南 |
| `clarifying_questions` | 信息不足时智能反问 |
| `context_transformation` | 文件转化、图片识别与索引维护 |
| `temporary_context_management` | 未解决问题记录 |

### 知识库

涵盖超星低代码全部核心引擎文档：表单引擎、审批引擎、数据工厂、图表引擎、聚合表、信息查询、业务流程管理等，附带 2000+ 参考截图。

## 项目结构

```
├── frontend/                  # Vue 3 前端
│   └── src/
│       ├── views/             # 页面组件 (ChatView / LoginView / AdminView...)
│       ├── api/               # API 封装 (chat / auth / admin)
│       ├── router/            # 路由定义 + 守卫
│       └── composables/       # 登录状态管理
├── backend/                   # FastAPI 后端
│   ├── main.py                # 应用入口
│   ├── config.py              # 全局配置
│   ├── database.py            # SQLite 初始化
│   ├── routers/               # API 路由 (chat / auth / admin / feedback)
│   ├── services/              # 业务服务 (agent / llm / search / skill...)
│   └── dependencies/          # 鉴权中间件
├── agent_config/              # AI Agent 配置
│   ├── agent.md               # Agent 角色定义与工作流
│   ├── skills/                # 技能定义 (Prompt + 脚本)
│   └── context/               # 知识库文档与图片资源
├── docs/                      # 项目文档 (PRD / 开发文档 / 设计稿)
└── debug/                     # 调试与测试脚本
```

## API 接口

### 对话 & 会话

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | AI 对话 (SSE 流式) |
| GET | `/api/sessions` | 会话列表 |
| POST | `/api/sessions` | 创建会话 |
| GET | `/api/sessions/{id}/messages` | 获取消息 |
| PATCH | `/api/sessions/{id}` | 修改标题 |
| DELETE | `/api/sessions/{id}` | 删除会话 |

### 用户认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/passport/cookie/login` | 用超星 Cookie 换取本地 JWT（带 token 走快路径） |
| GET | `/api/me` | 当前用户信息 |

> 原 `/api/register`、`/api/login` 已随账号密码体系下线。

### 反馈 & 管理

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/feedback` | 提交反馈 |
| GET | `/api/admin/accounts` | 账号管理 |
| GET | `/api/admin/feedbacks` | 反馈管理 |
| GET | `/api/admin/agent-config/tree` | Agent 配置树 |
