# 05 — 图片与 PDF 附件输入（多模态对话）开发文档

> **版本**：v1.0
> **最后更新**：2026-11-18
> **状态**：待开发
> **适用迭代**：阶段 5（对话输入框支持图片/PDF 附件、附件入库、多模态消息进入 Agent）
>
> **前置方案**：[图片输入改造方案](../design/design_specifications/图片输入改造方案.md)
> **适用模型**：`doubao-seed-2-1-lite-260915`（默认），图片与 PDF 均走同一模型链路

---

## 目录

1. [项目技术架构总览](#一项目技术架构总览)
2. [数据库设计](#二数据库设计)
3. [后端 API 接口完整定义](#三后端-api-接口完整定义)
4. [前端页面完整设计](#四前端页面完整设计)
5. [前后端交互完整流程](#五前后端交互完整流程)
6. [技术架构依赖清单](#六技术架构依赖清单)
7. [状态管理与全局配置](#七状态管理与全局配置)
8. [部署与构建说明](#八部署与构建说明)
9. [开发顺序建议](#九开发顺序建议)
10. [补充考量](#十补充考量)
11. [模型与附件格式确认](#十一模型与附件格式确认)
12. [验收清单](#十二验收清单)

---

## 一、项目技术架构总览

### 1.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              浏览器客户端                                     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ /chat  ChatView.vue（改造）                                             │  │
│  │  └─ 底部输入区（当前内联 textarea）                                     │  │
│  │       └─ ChatInput.vue（新建）                                          │  │
│  │          ├─ textarea（v-model="inputText"）                             │  │
│  │          ├─ AttachmentCard.vue（新建，v-for 附件）                       │  │
│  │          ├─ 隐藏 input[type=file]（accept=image/*,application/pdf）      │  │
│  │          ├─ 回形针按钮 + 状态文案                                        │  │
│  │          └─ 蓝色发送按钮（文案固定"发送"；流式时停止）                   │  │
│  └───────────────────────────────┬──────────────────────────────────────────┘  │
│                                  │                                            │
│  ┌───────────────────────────────▼──────────────────────────────────────────┐  │
│  │ 前端 API 层                                                               │  │
│  │  api/chat.ts（改造）：streamChat(sessionId, text, attachments)            │  │
│  │  api/attachments.ts（新建）：getAttachmentContent(messageId, attachmentId) │  │
│  │  api/auth.ts（已有）：authFetch 注入 Bearer Token + 401 跳转              │  │
│  └───────────────────────────────┬──────────────────────────────────────────┘  │
└──────────────────────────────────┼────────────────────────────────────────────┘
                                   │ HTTP JSON / SSE（Vite Proxy /api → :8000）
┌──────────────────────────────────▼────────────────────────────────────────────┐
│                          FastAPI 后端（:8000）                                 │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ 路由层 routers/                                                         │   │
│  │  chat.py（改造）                                                         │   │
│  │  ├─ POST /api/chat（改造）：接收 attachments，SSE 返回                    │   │
│  │  ├─ GET /api/sessions/{sid}/messages（改造）：返回 attachments            │   │
│  │  └─ GET /api/messages/{mid}/attachments/{aid}/content（新建）            │   │
│  └───────────────────────────────┬─────────────────────────────────────────┘   │
│                                  │                                             │
│  ┌───────────────────────────────▼─────────────────────────────────────────┐   │
│  │ 服务层 services/                                                         │   │
│  │  attachment_service.py（新建）                                            │   │
│  │  ├─ validate()：MIME/魔数/大小/像素预检                                   │   │
│  │  ├─ persist()：Base64 解码 + 落盘 + 元数据生成                             │   │
│  │  └─ resolve()：按 storage_ref 读取附件内容                                 │   │
│  │  message_content.py（新建）                                               │   │
│  │  └─ build_user_content()：图片→image_url，PDF→file part                   │   │
│  │  agent_service.py（改造）：payload 使用视觉模型，上下文截断兼容多模态       │   │
│  │  session_service.py（改造）：append_message 支持 attachments               │   │
│  └───────────────────────────────┬─────────────────────────────────────────┘   │
│                                  │                                             │
│  ┌───────────────────────────────▼─────────────────────────────────────────┐   │
│  │ 数据层                                                                   │   │
│  │  SQLite（data/app.db）：messages（+attachments 列）                       │   │
│  │  文件系统：backend/data/uploads/sessions/{sid}/messages/{mid}/...         │   │
│  │  火山方舟：POST /api/v3/chat/completions（已有地址，改造 payload）         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 技术栈明细

| 层级 | 技术选择 | 版本 | 用途 |
|------|---------|------|------|
| 前端框架 | Vue 3 (Composition API) | ^3.5.34 | 输入组件 + 消息渲染改造 |
| 前端语言 | TypeScript | ~6.0.2 | 附件类型定义与 API 类型安全 |
| 构建工具 | Vite | ^8.0.12 | 开发服务器 + `/api` 代理 |
| UI 组件库 | Element Plus | ^2.14.0 | `ElMessage` 提示；输入区仍手写 DOM 对齐参考样式 |
| 路由 | vue-router | ^4.6.4 | 现有 `/chat` 路由，不新增 |
| HTTP 客户端 | 原生 fetch | — | JSON + SSE 流式读取 |
| Markdown 渲染 | marked | — | AI 回复渲染，已有依赖 |
| 状态管理 | 组件内 ref + composable | — | `useAttachments()` 管理附件队列 |
| 后端框架 | FastAPI | — | 路由、Pydantic 校验、SSE |
| ASGI 服务器 | Uvicorn | — | 本地与生产运行 |
| 数据库 | SQLite | — | `data/app.db`，原生 sqlite3 |
| ORM | 无（原生 sqlite3） | — | 参数化 SQL，沿用现有方式 |
| 认证方式 | JWT (PyJWT) | ≥2.0 | `Bearer Token`，`dependencies/auth.py` |
| 加密方式 | bcrypt | ≥4.0 | 密码哈希，已有 |
| 配置管理 | python-dotenv + config.py | — | `.env` 新增附件与模型配置 |
| 文件存储 | 本地文件系统 | — | 首版落盘；P1 可替换 Files API/TOS |

> **无新增第三方依赖**。图片/PDF 均以 Base64 JSON 入站，不引入 `el-upload`、`python-multipart`、`pypdf` 等依赖。

---

## 二、数据库设计

### 2.1 改造表：`messages`（消息表）

#### 2.1.1 完整 DDL

```sql
-- 最终目标表结构（本迭代新增 attachments 列）
CREATE TABLE IF NOT EXISTS messages (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,  -- 消息 ID
    session_id        TEXT    NOT NULL,                   -- 关联 sessions.id
    role              TEXT    NOT NULL,                   -- user / assistant / system
    content           TEXT    NOT NULL,                   -- 纯文本正文；不含图片/PDF 原文
    reasoning_content TEXT    DEFAULT '',                 -- 思考过程
    steps             TEXT    DEFAULT '',                 -- 结构化步骤 JSON
    attachments       TEXT    DEFAULT '[]',               -- 【本次新增】附件元数据 JSON
    created_at        REAL    NOT NULL,                   -- 创建时间（Unix 秒）
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id, created_at);
```

#### 2.1.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `id` | INTEGER | ✅ | 自增主键；附件落盘路径使用 |
| `session_id` | TEXT | ✅ | 关联会话，用于归属校验 |
| `role` | TEXT | ✅ | `user` / `assistant` / `system` |
| `content` | TEXT | ✅ | 仅保存用户输入的纯文本；纯附件消息为 `''` |
| `reasoning_content` | TEXT | — | 思考过程，已有 |
| `steps` | TEXT | — | 结构化步骤 JSON，已有 |
| `attachments` | TEXT | ✅ | **本次新增**；JSON 数组，默认 `'[]'` |
| `created_at` | REAL | ✅ | 创建时间，已有 |

#### 2.1.3 `attachments` JSON 结构

```json
[
  {
    "id": "att_9f2c1a7b",
    "kind": "image",
    "name": "截图.png",
    "mime": "image/png",
    "size": 743296,
    "width": 1920,
    "height": 1080,
    "sha256": "3a7f...c91b",
    "created_at": 1763452800,
    "storage": {
      "type": "local",
      "ref": "sessions/{session_id}/messages/{message_id}/att_9f2c1a7b.png"
    }
  },
  {
    "id": "att_7d31b0aa",
    "kind": "pdf",
    "name": "产品说明.pdf",
    "mime": "application/pdf",
    "size": 2145321,
    "page_count": null,
    "sha256": "b1c4...9ae2",
    "created_at": 1763452801,
    "storage": {
      "type": "local",
      "ref": "sessions/{session_id}/messages/{message_id}/att_7d31b0aa.pdf"
    }
  }
]
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `id` | string | ✅ | 消息内唯一 ID，格式 `att_<hex8>` |
| `kind` | `image` \| `pdf` | ✅ | 附件类型，决定模型 part 形态 |
| `name` | string | ✅ | 用户原始文件名，仅展示 |
| `mime` | string | ✅ | `image/png` / `image/jpeg` / `image/webp` / `application/pdf` |
| `size` | number | ✅ | 原始字节数 |
| `width` / `height` | number | — | 图片宽高，PDF 可省略 |
| `page_count` | number \| null | — | PDF 页数；首版可为 `null` |
| `sha256` | string | ✅ | 完整性校验与去重排查 |
| `storage.type` | string | ✅ | 首版固定 `local`；P1 可为 `ark_file` / `tos` |
| `storage.ref` | string | ✅ | 相对 `UPLOAD_DIR` 的路径，不含用户输入文件名 |

#### 2.1.4 改造说明与兼容策略

| 变更类型 | 列名 | 说明 |
|---------|------|------|
| 新增 | `attachments` | 默认 `'[]'`，旧消息读取为空数组 |

**兼容策略**：

- 旧数据 `attachments IS NULL` 或 `''` 时，统一按 `[]` 处理；
- `messages.content` 语义不变，仍是纯文本，会话标题、`<task_result>` 过滤、Markdown 渲染逻辑不受影响；
- 附件不进入 `reasoning_content` 与 `steps`；
- `session_service.append_message()` 增加可选参数 `attachments`，返回值由 `None` 变为 `message_id`，旧调用方忽略返回值即可。

#### 2.1.5 DDL 迁移脚本

在 `backend/database.py::_run_migrations()` 的 `migrations` 列表中新增：

```python
("messages", "attachments", "TEXT DEFAULT '[]'"),
```

幂等机制沿用现有 `try/except sqlite3.OperationalError`，无需额外版本号表。

#### 2.1.6 ER 关系图

```
┌────────────────┐       1───N        ┌──────────────────────┐
│    sessions    │───────────────────▶│      messages         │
│ id (PK)        │                    │ id (PK)               │
│ user_id        │                    │ session_id (FK)       │
│ deleted_at     │                    │ content               │
└────────────────┘                    │ attachments (JSON)    │
                                      └──────────┬───────────────┘
                                                 │ 1───N（逻辑关联）
                                                 ▼
                                      ┌──────────────────────┐
                                      │ 本地文件（非 DB）      │
                                      │ {UPLOAD_DIR}/{ref}    │
                                      └──────────────────────┘
```

> 附件与消息是"JSON 内嵌 + 文件系统引用"的逻辑一对多关系，不新建 `attachments` 表，避免本迭代引入额外 JOIN 与迁移成本。

---

## 三、后端 API 接口完整定义

### 3.1 对话模块（改造）

**文件**：`backend/routers/chat.py` + `backend/services/agent_service.py` + `backend/services/message_content.py`（新建） + `backend/services/attachment_service.py`（新建）

#### 3.1.1 `POST /api/chat` — 发送文本/图片/PDF 并流式返回回答

**功能**：创建消息、保存附件、组装多模态上下文、启动 Agent 流式回答。

**认证**：可选 Bearer Token（`get_current_user` 返回 `Optional[dict]`）；未登录时沿用现有匿名会话逻辑。

**请求体 (Request Body)**：

```json
{
  "session_id": "8f3a1c...",
  "message": "这两张截图里的报错怎么解决？",
  "new_session": false,
  "attachments": [
    {
      "kind": "image",
      "name": "截图.png",
      "mime": "image/png",
      "size": 743296,
      "data_url": "data:image/png;base64,iVBORw0KGgo..."
    },
    {
      "kind": "pdf",
      "name": "产品说明.pdf",
      "mime": "application/pdf",
      "size": 2145321,
      "base64": "JVBERi0xLjQK..."
    }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `session_id` | string | ✅ | 会话 ID；`new_session=true` 时可为空 |
| `message` | string | — | 用户文本；纯附件消息可为空字符串 |
| `new_session` | boolean | — | 默认 `false`，新建会话时返回空 SSE + `X-Session-Id` |
| `attachments[].kind` | `image` \| `pdf` | ✅ | 附件类型 |
| `attachments[].name` | string | ✅ | 原始文件名，长度 ≤ 200 |
| `attachments[].mime` | string | ✅ | 与 kind 对应的 MIME |
| `attachments[].size` | integer | ✅ | 原始字节数 |
| `attachments[].data_url` | string | 条件 | `kind=image` 必填，完整 data URL |
| `attachments[].base64` | string | 条件 | `kind=pdf` 必填，前端传**裸 Base64**，后端转 data URL 后发给模型 |

**校验规则**：

| 字段 | 规则 | 错误提示 |
|------|------|---------|
| `message` | `message.strip()` 与 `attachments` 不可同时为空 | "消息内容不能为空" |
| `attachments` | 数量 ≤ 6 | "最多上传 6 个附件" |
| `attachments` | 原始总大小 ≤ 20 MB | "附件总大小不能超过 20MB" |
| `attachments[kind=pdf]` | 数量 ≤ 1 | "每次最多上传 1 个 PDF" |
| `attachments[kind=image]` | 单图 ≤ 10 MB | "图片不能超过 10MB" |
| `attachments[kind=pdf]` | 单 PDF ≤ 20 MB | "PDF 不能超过 20MB" |
| `data_url` | 匹配 `^data:image/(png\|jpeg\|webp);base64,` | "不支持的图片格式" |
| `base64` | 可解码且魔数为 `%PDF-` | "PDF 文件无效" |
| `name` | 不含 `/`、`\`、`..` | "文件名包含非法字符" |

**成功响应**：`200 OK`，`Content-Type: text/event-stream`，响应头 `X-Session-Id: <session_id>`。

**SSE 事件类型**（与现有完全一致，无新增事件）：

| event 类型 | data 结构 | 说明 |
|-----------|----------|------|
| `reasoning` | `{"content": "..."}` | 思考过程片段 |
| `task` | `{"type": "...", "result": "...", "query": "..."}` | 技能执行结果 |
| `content` | `{"content": "..."}` | 最终回答片段 |
| `done` | `{}` | 生成结束 |
| `error` | `{"error": "..."}` | 模型或后端错误 |
| `warning` | `{"content": "..."}` | 非致命提示 |

完整 SSE 流示例：

```text
event: reasoning
data: {"content": "<THINK_V2>需要先看截图中的报错位置..."}

event: task
data: {"type": "knowledge_retrieval", "result": "...", "query": "导出失败 权限"}

event: content
data: {"content": "根据截图，问题出在..."}

event: content
data: {"content": "你可以按以下步骤处理..."}

event: done
data: {}
```

**失败响应**：

| 场景 | 状态码 | 响应体 |
|------|--------|-------|
| 消息与附件均为空 | `422` | `{"detail": "消息内容不能为空"}` |
| 附件超限/格式错误 | `422` | `{"detail": "图片不能超过 10MB"}` |
| 会话不存在 | `404` | `{"detail": "session not found"}` |
| 会话已软删除 | `404` | `{"detail": "session not found"}` |
| `ARK_API_KEY` 未配置 | `500` | `{"detail": "ARK_API_KEY not configured"}` |

#### 3.1.2 `GET /api/sessions/{session_id}/messages` — 获取历史消息（改造）

**功能**：返回会话消息，包含每条 user 消息的附件元数据。

**认证**：沿用现有逻辑（当前未强制用户归属，本迭代不扩大改动范围；附件内容接口单独做归属校验）。

**查询参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:--:|--------|------|
| `limit` | integer | — | `50` | 返回条数，1–200 |
| `before_id` | integer | — | — | 分页游标 |

**成功响应**：`200 OK`

```json
{
  "session_id": "8f3a1c...",
  "has_more": false,
  "messages": [
    {
      "id": 128,
      "role": "user",
      "content": "这两张截图里的报错怎么解决？",
      "attachments": [
        {
          "id": "att_9f2c1a7b",
          "kind": "image",
          "name": "截图.png",
          "mime": "image/png",
          "size": 743296,
          "preview_url": "/api/messages/128/attachments/att_9f2c1a7b/content"
        }
      ],
      "created_at": 1763452800
    }
  ]
}
```

> `preview_url` 由后端拼接返回，前端不自行拼路径。

**失败响应**：`404 {"detail": "session not found"}`。

#### 3.1.3 `GET /api/messages/{message_id}/attachments/{attachment_id}/content` — 获取附件内容（新建）

**功能**：带鉴权地返回附件二进制，用于历史卡片预览/下载。

**认证**：需要 Bearer Token；校验消息所属会话的 `user_id` 与当前用户一致。

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `message_id` | integer | ✅ | `messages.id` |
| `attachment_id` | string | ✅ | 附件 `id` |

**成功响应**：`200 OK`

- `Content-Type`: 附件 `mime`
- `Content-Disposition`: `inline; filename="<safe_name>"`
- Body: 文件字节流

**失败响应**：

| 场景 | 状态码 | 响应体 |
|------|--------|-------|
| 未登录 | `401` | `{"detail": "Not authenticated"}` |
| 消息不属于当前用户 | `403` | `{"detail": "forbidden"}` |
| 消息不存在 | `404` | `{"detail": "message not found"}` |
| 附件 ID 不存在 | `404` | `{"detail": "attachment not found"}` |
| 文件已清理 | `410` | `{"detail": "attachment expired"}` |

#### 3.1.4 路由汇总表

| 方法 | 路径 | 认证 | 模块 | 说明 |
|------|------|:--:|------|------|
| POST | `/api/chat` | 可选 | 对话 | 发送文本/图片/PDF，SSE 返回 |
| GET | `/api/sessions` | 可选 | 对话 | 会话列表，已有 |
| GET | `/api/sessions/{sid}/messages` | 可选 | 对话 | 历史消息，改造返回 attachments |
| GET | `/api/messages/{mid}/attachments/{aid}/content` | 必需 | 附件 | 附件内容读取，新建 |
| DELETE | `/api/sessions/{sid}` | 必需 | 对话 | 软删除会话，已有 |

---

## 四、前端页面完整设计

### 4.1 聊天输入组件 `ChatInput.vue`（新建）

**路由**：`/chat`
**文件**：`frontend/src/components/ChatInput.vue`
**参考原型**：[图片输入改造方案](../design/design_specifications/图片输入改造方案.md) 第十一章
**设计规范**：[设计规范](../design/design_specifications/设计规范.md)

#### 4.1.1 组件树

```
ChatView.vue（改造）
└─ ChatInput.vue（新建）
   ├─ div.chat-input-card
   │  ├─ div.attachment-list（v-if="attachments.length > 0"）
   │  │  └─ AttachmentCard.vue（新建，v-for="att in attachments" :key="att.id"）
   │  │     ├─ span.att-icon（IMG / PDF）
   │  │     ├─ span.att-name（单行省略）
   │  │     ├─ span.att-meta（"PNG · 727.35KB"）
   │  │     └─ button.att-remove（×，@click="remove(att.id)"）
   │  ├─ textarea.msg-input
   │  │  （v-model="inputText"，placeholder="请将文本粘贴到此处..."
   │  │   @keydown="handleKeydown"，@paste="handlePaste"，@drop="handleDrop"）
   │  ├─ div.input-footer
   │  │  ├─ button.btn-attach（回形针 SVG，@click="openFilePicker"）
   │  │  ├─ span.attach-status（"已上传 N 个文件" / "支持粘贴、拖拽或点击上传"）
   │  │  └─ button.btn-send
   │  │     （文案固定"发送"；isStreaming 时切换为停止方块）
   │  └─ input.file-input（hidden，type=file，multiple，
   │                      accept="image/png,image/jpeg,image/webp,application/pdf,.pdf")
   └─ ElMessage（格式/超限错误提示）
```

#### 4.1.2 交互逻辑

```text
用户操作
   ├─ Ctrl/Cmd + V 粘贴
   │    └─ clipboardData.items 中存在 image/* 或 application/pdf
   │         ├─ 是 → preventDefault() → 加入附件队列
   │         └─ 否 → 保持默认文本粘贴
   ├─ 点击回形针
   │    └─ 触发隐藏 input[type=file] → change → 加入附件队列
   ├─ 拖拽文件到输入卡片
   │    └─ dragover：显示蓝色虚线高亮
   │       drop：仅接收白名单 MIME → 加入附件队列
   ├─ 点击附件卡片 ×
   │    └─ 从队列移除 → revokeObjectURL（仅图片）
   └─ 点击"发送" / 按 Enter
        ├─ 正文或附件为空 → 按钮禁用，不发送
        └─ 非空 → emit('send', { text, attachments })
             ├─ 清空输入与附件队列
             └─ 调用现有 streamChat()，无识别/解析阶段
```

#### 4.1.3 前端校验规则

| 字段 | 规则 | 错误消息 | 触发时机 |
|------|------|---------|---------|
| 图片 MIME | 仅 `image/png` / `image/jpeg` / `image/webp` | "仅支持 PNG/JPEG/WebP 图片" | 粘贴/选择/拖放 |
| PDF MIME | `application/pdf` | "仅支持 PDF 文档" | 粘贴/选择/拖放 |
| 单图大小 | ≤ 10 MB | "图片不能超过 10MB" | 文件读取后 |
| 单 PDF 大小 | ≤ 20 MB | "PDF 不能超过 20MB" | 文件读取后 |
| 附件数量 | ≤ 6 | "最多上传 6 个附件" | 加入队列前 |
| PDF 数量 | ≤ 1 | "每次最多上传 1 个 PDF" | 加入队列前 |
| 附件总大小 | ≤ 20 MB | "附件总大小不能超过 20MB" | 加入队列前 |
| 文件名 | 不含 `/` `\` `..` | "文件名包含非法字符" | 加入队列前 |

#### 4.1.4 UI 组件映射

| 原 HTML 元素 | UI 组件 | 关键属性 |
|-------------|---------|---------|
| 发送按钮 | 原生 `<button>` | `:disabled="!canSend && !isStreaming"`，沿用现有 SVG |
| 回形针按钮 | 原生 `<button>` + 隐藏 `<input>` | `accept="image/png,image/jpeg,image/webp,application/pdf,.pdf" multiple` |
| 错误提示 | `ElMessage` | `type="warning"`，非阻塞 |
| 输入卡片 | 原生 `<div>` | 手写 CSS，对齐参考图 |

#### 4.1.5 改造清单

| 改造项 | 当前状态 | 目标状态 | 难度 |
|--------|---------|---------|:--:|
| 抽离输入区为 `ChatInput.vue` | 内联在 `ChatView.vue` | 独立组件 + `send` 事件 | 中 |
| 支持粘贴/拖拽/选择附件 | 无 | 三种入口 | 中 |
| 附件卡片展示 | 无 | 图片/PDF 区分图标与元信息 | 中 |
| 发送按钮文案 | 固定"发送" | 保持不变，不提供"开始识别" | 低 |
| 历史消息附件卡片 | 无 | 只读展示 + 鉴权预览 | 中 |
| `streamChat` 传附件 | 仅文本 | 增加 `attachments` 参数 | 低 |

#### 4.1.6 CSS 关键样式

| 区域 | 样式说明 |
|------|---------|
| 输入卡片 | `border: 1px solid var(--color-primary)`；`border-radius: var(--radius-lg)`；`background: var(--color-bg-card)` |
| 聚焦态 | `box-shadow: 0 0 0 3px rgba(43,103,255,.10)` |
| 附件卡片 | `background: var(--color-bg-hover)`；`border-radius: var(--radius-md)`；图片图标青绿色，PDF 图标红色 |
| 状态文案 | `color: var(--color-text-tertiary)`；`font-size: 12px` |
| 发送按钮 | `background: var(--color-primary)`；禁用 `var(--color-text-disabled)`；流式停止 `var(--color-danger)` |
| 拖拽高亮 | `border-style: dashed` + `var(--color-primary-light)` 背景 |
| 错误卡片 | `border-color: var(--color-danger)` + 浅红背景 |

> 所有色值通过 CSS 变量引用，不硬编码新色值。

### 4.2 消息渲染改造 `ChatView.vue`（改造）

**文件**：`frontend/src/views/ChatView.vue`

- 用户消息 `UIMessage` 增加 `attachments?: ChatAttachment[]`；
- 用户气泡中在文本下方渲染只读附件卡片；
- 点击卡片调用 `getAttachmentContent(message.id, att.id)` 得到 Blob URL 并打开现有图片预览遮罩；PDF 使用 `window.open(blobUrl)`；
- 流式生成期间不显示附件删除入口；
- 现有检索图片预览逻辑保持不变。

---

## 五、前后端交互完整流程

### 5.1 发送图文/PDF 附件完整时序

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       发送多模态附件 + SSE 对话                            │
│                                                                          │
│  前端 ChatInput.vue              后端 FastAPI               Ark           │
│  ─────────────────               ────────────               ───           │
│                                                                          │
│  1. 用户粘贴/选择/拖入附件                                                │
│  2. 图片→dataURL；PDF→裸 Base64 入站                                     │
│  3. 点击"发送"（文案始终为发送）                                          │
│  4. ── POST /api/chat ─────────▶                                         │
│     Body: { session_id, message, attachments }                           │
│                                  5. 校验 MIME/魔数/大小                  │
│                                  6. 生成 attachment_id                   │
│                                  7. 落盘 + 写 messages.attachments        │
│                                  8. build_user_content()                 │
│                                  9. truncate_messages()                  │
│                                 10. ── chat/completions ───────────────▶ │
│                                 11. ◀─── SSE delta ───────────────────── │
│ 12. ◀── SSE: reasoning/task/content/done ──                              │
│ 13. 原样走现有流式渲染与思考过程                                          │
│ 14. 清空输入附件；刷新会话列表                                            │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.2 历史附件回显与鉴权读取时序

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          历史附件回显                                     │
│                                                                          │
│  前端 ChatView.vue                 后端 FastAPI                           │
│  ─────────────────                 ────────────                           │
│                                                                          │
│  1. ── GET /api/sessions/{sid}/messages ──▶                              │
│  2. ◀── messages[].attachments（含 preview_url） ──                      │
│  3. 渲染只读附件卡片                                                     │
│  4. 用户点击卡片 → GET preview_url ────────▶                             │
│  5.                                          校验 Token 与会话归属        │
│  6.                                          解析 storage.ref 读取文件    │
│  7. ◀── 200 application/pdf 或 image/* ──────                            │
│  8. 图片 → 复用现有预览遮罩；PDF → 新窗口打开 Blob URL                    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.3 重新生成 / 继续追问时的附件回注

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     附件回注（Chat API 无状态）                            │
│                                                                          │
│  后端 agent_service.py                                                    │
│  ─────────────────────                                                    │
│  1. 历史消息中的 attachments 元数据 → resolve(storage.ref)                │
│  2. 图片 → image_url part（data URL）                                     │
│  3. PDF  → file part（file_data 带 data:application/pdf;base64, 前缀）    │
│  4. 与当前轮用户文本一起重新构造 messages[].content 数组                  │
│  5. 每轮 Agent 调用都重新传入附件，不依赖模型记住上一轮                   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.4 API 请求 Token 注入与 401 处理

沿用 `frontend/src/api/auth.ts::authFetch()`：所有新接口通过 `authFetch` 请求；响应 `401` 时清除 `auth_token`/`user_info` 并跳转 `/login`。`streamChat()` 当前已自行注入 Token，改造时保持不变。

---

## 六、技术架构依赖清单

### 6.1 前端新增依赖

无需新增。现有 `Vue 3 + TypeScript + Vite + Element Plus` 已满足文件读取、Base64 转换、提示与样式需求。

### 6.2 后端新增依赖

无需新增。Base64 解码使用 Python 标准库 `base64`，魔数校验使用文件头字节比对，文件读写使用 `pathlib`。

> `pypdf` 仅作为未来精确统计 PDF 页数的可选项，本迭代不引入。

### 6.3 新增文件清单

| 文件路径 | 说明 | 优先级 |
|---------|------|:--:|
| `frontend/src/components/ChatInput.vue` | 附件输入组件 | 🔴 高 |
| `frontend/src/components/AttachmentCard.vue` | 附件卡片（输入区/历史区复用） | 🔴 高 |
| `frontend/src/composables/useAttachments.ts` | 附件队列、校验与转换逻辑 | 🔴 高 |
| `frontend/src/api/attachments.ts` | 附件内容读取 API | 🟡 中 |
| `backend/services/attachment_service.py` | 校验、落盘、解析 | 🔴 高 |
| `backend/services/message_content.py` | 多模态 content 构造与计权 | 🔴 高 |

### 6.4 改造现有文件清单

| 文件路径 | 改造内容 | 优先级 |
|---------|---------|:--:|
| `frontend/src/views/ChatView.vue` | 替换底部输入区；消息气泡渲染附件 | 🔴 高 |
| `frontend/src/api/chat.ts` | `ChatMessage` 增加 attachments；`streamChat()` 增加附件参数 | 🔴 高 |
| `backend/routers/chat.py` | `ChatRequest` 增加 attachments；历史接口返回附件；新增内容接口 | 🔴 高 |
| `backend/services/session_service.py` | `append_message()` 支持 attachments 并返回 message_id | 🔴 高 |
| `backend/services/agent_service.py` | 多模态 payload、视觉模型配置、截断兼容 | 🔴 高 |
| `backend/database.py` | `messages.attachments` 列迁移 | 🔴 高 |
| `backend/config.py` | 模型与附件配置 | 🟡 中 |
| `backend/main.py` | 注册附件路由（如单独 router） | 🟡 中 |
| `agent_config/agent.md` | 多模态消息通用规则 | 🟡 中 |
| `frontend/src/style.css` | 必要时补充卡片图标色变量引用 | 🔵 低 |

### 6.5 环境变量新增

```bash
# 视觉/文本模型（默认均为官方建议迁移模型，避开 260215 的 2026-11-24 EOS）
ARK_VISION_MODEL=doubao-seed-2-1-lite-260915
ARK_TEXT_MODEL=doubao-seed-2-1-lite-260915

# 图片理解精细度：low / high / xhigh
ARK_IMAGE_DETAIL=high

# 附件落盘根目录（相对 backend/）
UPLOAD_DIR=data/uploads

# 单图片/单 PDF/总大小限制（字节）
MAX_IMAGE_SIZE=10485760
MAX_PDF_SIZE=20971520
MAX_ATTACHMENTS_TOTAL_SIZE=20971520
MAX_ATTACHMENTS_COUNT=6

# 附件保留天数；0 表示不自动清理
ATTACHMENT_RETENTION_DAYS=30
```

---

## 七、状态管理与全局配置

### 7.1 前端类型定义

文件：`frontend/src/api/chat.ts`（改造）

```typescript
export type AttachmentKind = 'image' | 'pdf'

export interface ChatAttachment {
  id: string
  kind: AttachmentKind
  name: string
  mime: string
  size: number
  width?: number
  height?: number
  page_count?: number | null
  sha256?: string
  storage?: { type: string; ref: string }
  preview_url?: string
}

export interface PendingAttachment {
  id: string
  kind: AttachmentKind
  name: string
  mime: string
  size: number
  previewUrl?: string
  dataUrl?: string
  base64?: string
  status: 'ready' | 'error'
  error?: string
}

export interface ChatMessage {
  id?: number
  role: 'user' | 'assistant' | 'system'
  content: string
  attachments?: ChatAttachment[]
  reasoning_content?: string
  steps?: ChatStep[]
  tasks?: ChatTask[]
  created_at?: number
}
```

### 7.2 附件队列 composable

文件：`frontend/src/composables/useAttachments.ts`（新建，核心逻辑示意）

```typescript
import { ref } from 'vue'
import type { PendingAttachment } from '../api/chat'

const ALLOWED_IMAGE_MIME = ['image/png', 'image/jpeg', 'image/webp']
const MAX_IMAGE_SIZE = 10 * 1024 * 1024
const MAX_PDF_SIZE = 20 * 1024 * 1024
const MAX_TOTAL_SIZE = 20 * 1024 * 1024
const MAX_COUNT = 6

export function useAttachments() {
  const attachments = ref<PendingAttachment[]>([])

  function reset() {
    attachments.value.forEach(a => {
      if (a.previewUrl) URL.revokeObjectURL(a.previewUrl)
    })
    attachments.value = []
  }

  async function addFiles(files: File[]) {
    for (const file of files) {
      if (attachments.value.length >= MAX_COUNT) break

      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
      const isImage = ALLOWED_IMAGE_MIME.includes(file.type)

      if (!isImage && !isPdf) continue
      if (isPdf && attachments.value.some(a => a.kind === 'pdf')) continue
      if (file.size > (isPdf ? MAX_PDF_SIZE : MAX_IMAGE_SIZE)) continue

      const item: PendingAttachment = {
        id: `att_${crypto.randomUUID().slice(0, 8)}`,
        kind: isPdf ? 'pdf' : 'image',
        name: file.name,
        mime: isPdf ? 'application/pdf' : file.type,
        size: file.size,
        status: 'ready',
      }

      if (isImage) {
        item.previewUrl = URL.createObjectURL(file)
        item.dataUrl = await readAsDataURL(file)
      } else {
        item.base64 = await readAsBase64(file)
      }

      attachments.value.push(item)
    }
  }

  return { attachments, addFiles, reset }
}

function readAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

function readAsBase64(file: File): Promise<string> {
  return readAsDataURL(file).then(dataUrl => dataUrl.split(',')[1] || '')
}
```

### 7.3 CSS 变量注入

沿用 `frontend/src/style.css:1-32`，本迭代不新增色值，仅引用既有变量：

```css
:root {
  --color-primary: #2B67FF;
  --color-primary-light: #EBF2FF;
  --color-danger: #F53F3F;
  --color-text-tertiary: #717989;
  --color-bg-hover: #F5F6FA;
  --radius-md: 8px;
  --radius-lg: 12px;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.06);
  --spacing-sm: 8px;
  --spacing-md: 12px;
}
```

### 7.4 UI 框架主题覆盖

现有 `frontend/src/style.css:55-58` 已覆盖 Element Plus 主按钮色，本迭代仅使用 `ElMessage`，无需新增主题覆盖。

---

## 八、部署与构建说明

### 8.1 开发环境运行命令

```bash
# 后端
cd backend
python -m venv .venv
. .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

### 8.2 生产构建命令

```bash
cd frontend
npm run build
```

后端仍通过 Uvicorn 启动，静态资源与 SPA fallback 沿用 `backend/main.py` 现有逻辑。

### 8.3 数据库迁移说明

- 迁移在 `backend/database.py::init_db()` 启动时自动执行；
- 新增迁移项 `("messages", "attachments", "TEXT DEFAULT '[]'")`；
- 旧数据默认 `'[]'`，无需手工回填；
- 迁移失败不会影响已有 `content` 字段读取。

### 8.4 附件目录

```bash
mkdir -p backend/data/uploads/sessions
```

服务端首次落盘时也会自动创建目录。部署时需确保运行用户对该目录具备读写权限。

---

## 九、开发顺序建议

| 阶段 | 任务 | 优先级 | 依赖 |
|:--:|------|:--:|------|
| 1 | `database.py` 增加 `messages.attachments` 迁移 | 🔴 高 | — |
| 2 | 新建 `attachment_service.py`：校验 + 落盘 + resolve | 🔴 高 | 1 |
| 3 | 新建 `message_content.py`：图片/PDF part 构造与计权 | 🔴 高 | 2 |
| 4 | 改造 `session_service.append_message()` 支持 attachments | 🔴 高 | 1 |
| 5 | 改造 `POST /api/chat`：DTO + 校验 + 落库 + 多模态消息 | 🔴 高 | 2,3,4 |
| 6 | 改造 `agent_service.py`：视觉模型配置 + 截断兼容 | 🔴 高 | 3,5 |
| 7 | 新增 `GET /api/messages/{mid}/attachments/{aid}/content` | 🟡 中 | 2,5 |
| 8 | 改造 `GET /api/sessions/{sid}/messages` 返回 attachments | 🟡 中 | 5 |
| 9 | 新建 `ChatInput.vue` / `AttachmentCard.vue` / `useAttachments.ts` | 🔴 高 | — |
| 10 | 改造 `ChatView.vue` 接入输入组件与历史附件卡片 | 🔴 高 | 9 |
| 11 | 改造 `api/chat.ts` 与 `streamChat()` 载荷 | 🔴 高 | 9 |
| 12 | 新增 `api/attachments.ts` 与 Blob 预览 | 🟡 中 | 7,10 |
| 13 | `agent.md` 增加多模态通用规则 | 🟡 中 | 6 |
| 14 | 图片链路端到端联调 | 🔴 高 | 5,6,10,11 |
| 15 | PDF 冒烟验证（P-001/P-003）并放开 PDF 入口 | 🟡 中 | 14 |
| 16 | 附件清理任务与保留策略 | 🔵 低 | 7 |
| 17 | Files API（`file_id`）迁移，减少重复 Base64 | 🔵 低 | 14 |

---

## 十、补充考量

### 10.1 错误处理与边界情况

| 场景 | 前端处理 | 后端处理 |
|------|---------|---------|
| Token 过期 / 无效 | `authFetch` 清除登录态并跳转 `/login` | `401` |
| 网络中断 | 保留附件队列，回答气泡显示"重新生成" | `AbortController` 中止 SSE |
| 业务校验失败 | 卡片内错误提示 / `ElMessage` | `422` 中文 detail |
| 资源不属于当前用户 | 不展示预览 | `403 forbidden` |
| 流式数据传输中断 | 保留已渲染内容，显示重新生成 | SSE 结束前不落 assistant 消息 |
| 空数据列表 | 输入区保持空态 | 不创建消息 |
| 并发冲突 | 发送中禁用输入区 | SQLite 用 `with get_db()` 串行写入 |
| XSS 防护 | 文件名 `textContent` 渲染，禁止 `v-html` | 落盘文件名服务端生成 |
| 数据库并发锁 | 重试提示 | WAL 模式 + 短事务 |
| 附件文件缺失 | 卡片显示"图片已过期" | `410 attachment expired` |
| 加密/损坏 PDF | 卡片显示"PDF 文件无效" | 魔数校验失败 `422` |
| 多图/多 PDF 超限 | 第 N 个拒绝加入队列 | `422` 兜底 |

### 10.2 安全性关注点

| 关注点 | 措施 |
|--------|------|
| 密码存储 | 沿用 bcrypt 加盐哈希，本迭代不改动 |
| Token 存储 | `localStorage auth_token`，`authFetch` 统一注入 |
| Token 有效期 | 沿用现有 JWT 配置 |
| XSS | 附件名用文本节点渲染；Markdown 渲染沿用现有清洗策略 |
| CSRF | 统一 Bearer Token + CORS 白名单，不使用 Cookie 鉴权 |
| SQL 注入 | 全程参数化 SQL |
| 路径穿越 | 落盘路径只由服务端生成，`storage.ref` 不接受客户端路径 |
| 敏感信息保护 | 附件内容接口做会话归属校验；禁止公开静态目录 |
| CORS | 沿用 `backend/main.py` 现有配置 |
| 文件大小 DoS | 前端 + 后端双重限制；Base64 解码前先校验声明大小 |
| 模型数据外发 | 在界面提示"附件将发送给大模型进行处理"（产品文案待确认） |

### 10.3 性能考量

| 场景 | 措施 |
|------|------|
| Base64 传输膨胀 | 前后端双重总量限制 20MB；P1 改 Files API `file_id` |
| 历史加载 | 历史接口只返回附件元数据与 `preview_url`，不返回 Base64 |
| 多轮 Agent 重复传附件 | `ATTACHMENT_KEEP_POLICY=all` 默认；压测后可切 `first_turn` |
| 上下文膨胀 | `content_weight()` 对图片按 1280 tokens、PDF 按页数估算计权 |
| 渲染优化 | 附件卡片使用 `v-for :key="att.id"`；图片 `objectURL` 及时 revoke |
| 磁盘增长 | `ATTACHMENT_RETENTION_DAYS` + 会话软删除联动清理 |
| 首包延迟 | 图片长边 > 2048px 的压缩策略列为后续优化 |

### 10.4 兼容性规划

| 项目 | 说明 |
|------|------|
| 数据库兼容 | `attachments` 默认 `'[]'`，旧消息无需回填 |
| API 向后兼容 | `attachments` 为可选字段；旧客户端只传 `message` 仍可用 |
| 前端兼容 | 老会话无 attachments 时不渲染附件卡片 |
| 模型兼容 | 无图片/PDF 时继续发送字符串 content，行为与改造前一致 |
| 初始数据方案 | 无需初始化附件数据 |

### 10.5 测试策略

| 测试类型 | 范围 | 工具 |
|---------|------|------|
| 后端单元测试 | `build_user_content()`、`content_weight()`、魔数校验、Data URL 解析 | pytest |
| API 集成测试 | `POST /api/chat` 带附件、历史接口、附件内容接口 | pytest + TestClient |
| SSE 流式测试 | `reasoning/content/done` 事件完整到达 | 现有 SSE 调试脚本 |
| 前端功能测试 | 粘贴/拖拽/选择/删除/发送/历史回显 | 手动 + Playwright（可选） |
| 多模态冒烟 | 图片/PDF/PDF+图片+文字 | 真实 Ark 调用 |
| 回归测试 | 现有 Top 30 文本问题、技能调用、思考过程 | 现有回归集 |

### 10.6 开发规范

- **命名规范**：Vue 组件 `PascalCase`，后端文件 `snake_case`，API 路径 `kebab-case`。
- **注释规范**：`attachment_service.py` 的魔数表、`message_content.py` 的 part 构造规则必须注释。
- **Git 提交规范**：`feat: 支持图片/PDF 附件输入`、`fix: 附件归属校验` 等，参考 `01_迭代开发规范.md`。
- **类型安全**：TypeScript 禁止 `any`，后端 Pydantic 覆盖所有请求/响应。
- **日志规范**：不打印 Base64 原文，仅打印附件 ID、MIME、大小。

---

## 十一、模型与附件格式确认

### 11.1 图片

```json
{
  "type": "image_url",
  "image_url": {
    "url": "data:image/png;base64,{base64_image}",
    "detail": "high"
  }
}
```

- 支持 `image/png` / `image/jpeg` / `image/webp`；
- 单图 ≤ 10 MB，请求体 ≤ 64 MB；
- 图片在前、文字在后；无文字时不追加 text part。

### 11.2 PDF

```json
{
  "type": "file",
  "file": {
    "file_data": "data:application/pdf;base64,{base64_pdf}",
    "filename": "产品说明.pdf"
  }
}
```

- `file_data` **必须带** `data:application/pdf;base64,` 前缀；这是方舟实测要求，与前端入站的裸 Base64 不同，由后端统一转换；
- `filename` 必填；
- 单 PDF ≤ 20 MB（首版限制；官方 Base64 上限 50 MB）；
- PDF 会被分页处理成多图，由视觉能力理解；官方未给明确页数上限。

### 11.3 完整 user message 示例

```json
{
  "role": "user",
  "content": [
    {
      "type": "file",
      "file": {
        "file_data": "data:application/pdf;base64,JVBERi0xLjQK...",
        "filename": "产品说明.pdf"
      }
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "data:image/png;base64,iVBORw0KGgo...",
        "detail": "high"
      }
    },
    {
      "type": "text",
      "text": "这两份材料里提到的导出失败怎么处理？"
    }
  ]
}
```

### 11.4 模型配置

```python
# backend/config.py
ARK_VISION_MODEL = os.environ.get("ARK_VISION_MODEL", "doubao-seed-2-1-lite-260915")
ARK_TEXT_MODEL = os.environ.get("ARK_TEXT_MODEL", "doubao-seed-2-1-lite-260915")
ARK_IMAGE_DETAIL = os.environ.get("ARK_IMAGE_DETAIL", "high")
```

> `doubao-seed-2-0-pro-260215` 于 2026-11-24 14:00 EOS，不作为默认模型。

---

## 十二、验收清单

### 12.1 功能验收

| 编号 | 场景 | 通过标准 |
|------|------|---------|
| V-001 | 纯文本对话 | 与改造前完全一致 |
| V-002 | 2 张 PNG 提问 | 卡片样式正确，按钮仍为"发送"，模型回答与图片相关 |
| V-003 | 仅图片无文字 | 正常发送，不注入识别指令 |
| V-004 | 图片 + 文字 | 回答同时覆盖图片与文字 |
| V-005 | PDF + 文字 | 回答覆盖 PDF 内容 |
| V-006 | PDF + 图片 + 文字 | 三类 part 均进入同一条 user message |
| V-007 | 刷新历史会话 | 附件卡片可回显与预览 |
| V-008 | 重新生成 | 后端重新注入附件 |
| V-009 | 超限/非法格式 | 前端拦截并提示，后端兜底 |
| V-010 | 流式生成中 | 按钮变停止，行为与改造前一致 |
| V-011 | 删除会话 | 元数据随消息清理，文件可被清理 |
| V-012 | 无识别流程 | 不出现"开始识别/解析中"状态，无新增技能/SSE 事件 |

### 12.2 PDF 专项验收

| 编号 | 输入 | 通过标准 |
|------|------|---------|
| P-001 | 单页文字型 PDF | 能回答 PDF 中明确事实 |
| P-002 | 扫描版 PDF | 能读出主要文字；不清晰时说明看不清 |
| P-003 | 10–20 页 PDF | 跨页汇总不出现明显编造 |
| P-004 | 仅 PDF 无文字 | 正常发送并获得回应 |
| P-005 | 加密/损坏/>20MB PDF | 明确错误提示 |
| P-006 | PDF 历史回显 | 卡片可预览，刷新后仍在 |
| P-007 | PDF 重新生成 | `file` part 被重新注入 |

### 12.3 文档检查清单

- [x] 元信息完整（版本、日期、状态、迭代）
- [x] 架构图覆盖浏览器 → API → 路由 → 服务 → 数据
- [x] 数据库表有 DDL + 字段说明 + ER 图
- [x] 每个接口有功能、认证、请求体、成功/失败响应
- [x] SSE 接口有事件表与流示例
- [x] 前端组件有组件树、交互逻辑、校验规则
- [x] 核心流程有时序图
- [x] 依赖清单完整
- [x] 开发顺序按依赖排序
- [x] 补充考量覆盖错误、安全、性能、兼容、测试、规范
- [x] 代码块标注语言
- [x] 无硬编码新增色值，全部引用 CSS 变量
