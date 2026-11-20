# 08 — 不满意回答对话预览 Markdown 渲染 开发文档

> **版本**：v1.0
> **最后更新**：2026-11-20
> **状态**：待开发
> **适用迭代**：阶段 8（管理端「不满意回答」预览区 Markdown 渲染，纯前端展示层改造）
>
> **前置需求**：[08_不满意回答对话预览Markdown渲染.md](../prd/08_不满意回答对话预览Markdown渲染.md)
> **基线开发文档**：[03_管理员后台页.md](./03_管理员后台页.md)、[02_客服对话页.md](./02_客服对话页.md)
> **编写规范**：[开发文档规范.md](./开发文档规范.md)

---

## 目录

1. [项目技术架构总览](#一项目技术架构总览)
2. [数据库设计](#二数据库设计)
3. [后端 API 接口完整定义](#三后端-api-接口完整定义)
4. [前端页面完整设计](#四前端页面完整设计)
5. [前后端交互完整流程](#五前后端交互完整流程)
6. [技术架构依赖清单](#六技术架构依赖清单)
7. [状态管理与全局配置](#七状态管理与全局配置)
8. [部署与构建说明（沿用现有）](#八部署与构建说明沿用现有)
9. [开发顺序建议](#九开发顺序建议)
10. [补充考量](#十补充考量)
11. [验收清单](#十一验收清单)
12. [需求追踪矩阵](#十二需求追踪矩阵)

---

## 一、项目技术架构总览

### 1.1 整体架构图（聚焦本次变更）

本次变更**仅涉及前端展示层**：后端接口原样返回 Markdown 文本，前端在详情数据到达时调用已有的 `renderMarkdown()` 生成 HTML 并缓存，模板用 `v-html` 输出；复制按钮继续读取原始 `content`。

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              浏览器客户端                                     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ /admin → AdminView.vue（已有，无改动）                                   │  │
│  │  └─ FeedbackTab.vue（改造）                                              │  │
│  │      ├─ selectFeedback()：详情到达后逐条 m → _renderedHtml（新增）        │  │
│  │      ├─ 消息气泡：{{ content }} → v-html="_renderedHtml"（改造）         │  │
│  │      ├─ copyMessage(msg.content)：继续复制原文（无改动）                  │  │
│  │      └─ <style scoped>：新增 .chat-bubble :deep(...) 排版规则（新增）      │  │
│  │                                                                          │  │
│  │  components/messageUtils.ts（已有，无改动，仅复用）                        │  │
│  │  └─ renderMarkdown()：marked.parse + breaks/gfm + 图片路径改写 + 异常兜底   │  │
│  │                                                                          │  │
│  │  api/admin.ts（已有，无改动）                                             │  │
│  │  └─ getFeedbackDetail() → 返回 messages，content 为原始 Markdown          │  │
│  └───────────────────────────────┬──────────────────────────────────────────┘  │
│                                  │ HTTP JSON（Vite Proxy /api → :8000）        │
└──────────────────────────────────┼────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼────────────────────────────────────────────┐
│                          FastAPI 后端（:8000，本次无改动）                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  routers/feedback.py（已有，无改动）                                     │   │
│  │  └─ GET /api/admin/feedbacks/{id}：SELECT messages → 原样返回 content    │   │
│  └───────────────────────────────┬─────────────────────────────────────────┘   │
│  ┌───────────────────────────────▼─────────────────────────────────────────┐   │
│  │ 数据层（已有，无表结构变更）                                              │   │
│  │  SQLite：messages.content TEXT 存原始 Markdown（不转义、不转换）           │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────┘
```

**数据流向说明**：

- 后端 `content` 始终是原始 Markdown，不因本次改造产生任何变化（PRD G4）；
- 渲染发生在前端**详情数据到达时一次性预计算**，结果缓存在消息的 `_renderedHtml` 字段，避免拖拽分隔条等无关重渲染导致重复解析；
- 复制链路与渲染链路分离：`v-html` 只读 `_renderedHtml`，`copyMessage()` 只读 `content`。

### 1.2 技术栈明细

| 层级 | 技术选择 | 版本 | 用途 |
|------|---------|------|------|
| 前端框架 | Vue 3 (Composition API) | ^3.5.34 | `ref` 缓存渲染结果；`v-html` 输出富文本 |
| 前端语言 | TypeScript | ~6.0.2 | `Message` 接口新增可选字段 `_renderedHtml` |
| 构建工具 | Vite | ^8.0.12 | 开发服务器 + `/api` 代理，无变化 |
| UI 组件库 | Element Plus | ^2.14.0 | 沿用现有 `el-select` / `el-tag` / `ElMessage`，无新增组件 |
| 路由 | vue-router | ^4.6.4 | 现有 `/admin` 路由，不新增 |
| HTTP 客户端 | 原生 fetch | — | 沿用 `adminAuthFetch()`，无改动 |
| Markdown 渲染 | `marked` | ^18.0.4 | 已在依赖清单中，通过 `renderMarkdown()` 间接使用 |
| 后端框架 | FastAPI | — | 无改动 |
| ASGI 服务器 | Uvicorn | — | 无改动 |
| 数据库 | SQLite | — | 无表结构变更 |
| ORM | 无（原生 sqlite3） | — | 无改动 |
| 认证方式 | 管理员 Token（JWT，localStorage `admin_token`） | — | 无改动 |
| 配置管理 | python-dotenv + config.py | — | 无改动 |

> ✅ **无新增第三方依赖**：`marked` 已在 `frontend/package.json:13` 中，本次仅复用现有封装。

---

## 二、数据库设计

### 2.1 结论：无表结构变更

本次为纯前端展示层改造（PRD G4、N5），**不新增表、不新增字段、不写迁移脚本、不修改任何数据**。

| 表 | 本次状态 | 说明 |
|----|---------|------|
| `messages` | 已有，无改动 | `content` 仍存 LLM 回答/用户输入的原始 Markdown；`renderMarkdown()` 只在前端内存生成 HTML，不回写 |
| `feedback` | 已有，无改动 | — |
| `sessions` / `users` | 已有，无改动 | — |

### 2.2 复用的字段（现有 DDL，摘自 `backend/database.py:62`）

```sql
CREATE TABLE IF NOT EXISTS messages (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT    NOT NULL,          -- 所属会话（本次按此查询详情消息）
    role              TEXT    NOT NULL,          -- 'user' / 'assistant'，决定气泡样式
    content           TEXT,                      -- 本次输入：原始 Markdown 文本，不做转换
    reasoning_content TEXT,                      -- 本次不涉及（PRD N2）
    steps             TEXT,                      -- 本次不涉及
    attachments       TEXT,                      -- 本次不涉及
    created_at        REAL    NOT NULL
);
```

| 字段 | 类型 | 必填 | 本次说明 |
|------|------|:--:|---------|
| `id` | INTEGER | ✅ | 消息列表 `v-for` 的 key |
| `role` | TEXT | ✅ | `user` 走蓝底气泡，其余走白底气泡；两者都做 Markdown 渲染 |
| `content` | TEXT | ❌ | `renderMarkdown()` 的输入；为空时渲染为空串（PRD R4） |

### 2.3 ER 关系（确认无新表）

```
┌──────────────────────┐          ┌──────────────────────────────────────┐
│ feedback             │          │ messages                             │
├──────────────────────┤          ├──────────────────────────────────────┤
│ id        INTEGER PK │ 1 ─── 1  │ id           INTEGER PK AUTOINCREMENT │
│ session_id TEXT      │◀────────▶│ session_id   TEXT  ← 详情查询条件      │
│ user_id   INTEGER    │          │ role         TEXT                     │
│ status    TEXT       │          │ content      TEXT  ← Markdown 原文    │
└──────────────────────┘          └──────────────────────────────────────┘

详情接口按 fb.session_id 取 messages，按 created_at ASC 排序，原样返回。
```

---

## 三、后端 API 接口完整定义

### 3.1 路由总览

| 方法 | 路径 | 认证 | 本次状态 | 说明 |
|------|------|:--:|---------|------|
| `GET` | `/api/admin/feedbacks/{id}` | ✅ 管理员 | 已有，**无改动** | 返回 `messages[].content`（原始 Markdown），是本次渲染的数据来源 |
| `GET` | `/api/admin/feedbacks` | ✅ 管理员 | 已有，无改动 | 左侧列表，不渲染 Markdown |
| `POST` | `/api/admin/feedbacks/{id}/resolve` | ✅ 管理员 | 已有，无改动 | 改写入库，仍写原始 Q/A 文本 |

> ✅ **本次无新增、无改造后端接口**。渲染完全在前端完成；后端不返回 HTML，避免展示层与数据层耦合。

### 3.2 `GET /api/admin/feedbacks/{id}` — 反馈详情（已有，无改动）

**文件**：`backend/routers/feedback.py:118`

**功能**：按反馈 ID 查询反馈元信息与对应会话的完整消息记录。

**认证**：`Depends(require_admin)`，需 `admin_token`。

**查询参数**：无（路径参数 `feedback_id: int`）。

**成功响应**：`200`

```json
{
  "ok": true,
  "data": {
    "feedback": { "id": 12, "session_id": "5f8a...", "user_id": 3, "status": "pending", "created_at": 1750000000, "username": "用户A" },
    "messages": [
      { "id": 101, "role": "user",      "content": "退款流程是什么？", "reasoning_content": "", "created_at": 1750000001 },
      { "id": 102, "role": "assistant", "content": "## 退款流程\n**步骤 1**：提交申请\n- 订单中心\n- 填写原因", "reasoning_content": "", "created_at": 1750000002 }
    ]
  }
}
```

> 📌 `messages[].content` 是**原始 Markdown**（仅标准 JSON 字符串转义），前端 `renderMarkdown()` 负责解析。此契约与 `GET /api/sessions/{id}/messages` 一致，用户端已按此方式渲染。

**失败响应**：`404 {"detail": "反馈不存在"}`；`401` 由 Token 校验中间件处理。前端统一走 `catch → ElMessage.error('加载反馈详情失败')`。

---

## 四、前端页面完整设计

### 4.1 管理端后台 `frontend/src/views/admin/FeedbackTab.vue`（改造）

**路由**：`/admin`（`AdminView.vue` 内 Tab `feedback`，无独立路由）
**文件**：`frontend/src/views/admin/FeedbackTab.vue`
**参考原型**：[03_管理员后台页.md](../prd/03_管理员后台页.md) §六
**需求文档**：[08_不满意回答对话预览Markdown渲染.md](../prd/08_不满意回答对话预览Markdown渲染.md) §四

#### 4.1.1 组件树（仅标出本次变更节点）

```
FeedbackTab.vue
├── div.feedback-list-panel                       （无改动）
│   └── ... 筛选 / 日期分组 / 反馈条目
└── div.feedback-detail-panel  v-if="selectedFeedbackId"
    └── div.feedback-conversation
        └── div.conversation-messages  v-loading="loadingDetail"
            └── div.chat-bubble-row    v-for="msg in messages"  【循环体】
                ├── div.chat-bubble-avatar               （无改动：👤 / 🤖）
                └── div.chat-bubble-wrapper
                    ├── div.chat-bubble                   【改造】
                    │   └── v-html="msg._renderedHtml"     【新增】替代 {{ msg.content }}
                    └── button.chat-msg-copy-btn          （无改动）
                        └── @click="copyMessage(msg.content)"  ← 仍读原文
```

#### 4.1.2 交互逻辑（文本流程图）

```
管理员点击左侧反馈条目 selectFeedback(fb)
    → messages.value = []（清空，避免残留上一条对话）
    → getFeedbackDetail(fb.id) → 后端返回 messages（content 为原始 Markdown）
    → messages.value = data.data.messages.map(m => ({
          ...m,
          _renderedHtml: renderMarkdown(m.content)    ← 【新增】一次性预计算
      }))
    → qaPairs.value 仍由 data.data.messages 原文生成   ← 【无改动】关键：不用渲染结果
    → 模板 v-html 插入 HTML → 浏览器渲染为富文本气泡

鼠标 hover 气泡 → 复制按钮 opacity 0 → 1
    → 点击 📋 → copyMessage(msg.content)
    → navigator.clipboard.writeText(原文)             ← 【无改动】含 # ** 换行等标记
```

#### 4.1.3 前端校验规则

| 场景 | 规则 | 处理 |
|------|------|------|
| `content` 为空 / 空白 | 渲染结果为空串 | 气泡正常占位，无报错（PRD R4） |
| `renderMarkdown()` 抛错 | 工具函数 `try/catch` 兜底返回原文 | 页面不崩溃（PRD R5） |
| `messages` 切换 | 先清空再赋值，渲染缓存随新对象重建 | 无上一条对话残留 |
| 复制内容 | 只能读 `msg.content`，禁止读 `_renderedHtml` | 保证剪贴板为原始 Markdown（PRD G3） |

#### 4.1.4 改造清单

| 改造项 | 当前状态 | 目标状态 | 难度 |
|--------|---------|---------|:--:|
| `Message` 接口 | 4 个字段 | 新增可选 `_renderedHtml?: string` | 低 |
| `renderMarkdown` 引入 | 不存在 | 从 `../../components/messageUtils` 具名导入 | 低 |
| `selectFeedback()` 赋值逻辑 | `messages.value = data.data.messages` | `map()` 后附带 `_renderedHtml` 缓存 | 低 |
| 消息气泡模板 | `{{ msg.content }}` 纯文本插值 | `v-html="msg._renderedHtml ?? ''"` | 低 |
| 复制按钮 | `copyMessage(msg.content)` | **无需改动** | — |
| `qaPairs` 原文生成 | 使用 `data.data.messages` | **无需改动**（仍用原文） | — |
| `<style scoped>` | 无 Markdown 样式 | 新增 `.chat-bubble :deep(...)` 规则 + 用户气泡反色覆盖 | 中 |
| 后端 / API 层 / 路由 | — | **无需改动** | — |

#### 4.1.5 关键代码 — `<script setup>` 部分

```typescript
// frontend/src/views/admin/FeedbackTab.vue — 顶部新增导入
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getFeedbacks, getFeedbackDetail, resolveFeedback } from '../../api/admin'
import { renderMarkdown } from '../../components/messageUtils'   // 【新增】

interface Message {
  id: number
  role: string
  content: string
  reasoning_content: string
  created_at: number
  _renderedHtml?: string                                          // 【新增】渲染结果缓存
}
```

```typescript
// selectFeedback() — 仅替换 messages 赋值那一行
async function selectFeedback(fb: FeedbackItem) {
  selectedFeedbackId.value = fb.id
  loadingDetail.value = true
  messages.value = []

  try {
    const resp = await getFeedbackDetail(fb.id)
    const data = await resp.json()
    if (data.ok) {
      feedbackDetail.value = data.data.feedback
      // 【改造】详情到达时一次性渲染并缓存；content 原文保持不变
      messages.value = (data.data.messages as Message[]).map((m) => ({
        ...m,
        _renderedHtml: renderMarkdown(m.content),
      }))

      // 【无改动】自动 Q&A 仍基于原始 messages 生成，读取的是 m.content 原文
      const userMessages = data.data.messages.filter((m: Message) => m.role === 'user')
      qaPairs.value = userMessages.map((m: Message) => ({
        question: m.content,
        answer: '',
      }))
      if (qaPairs.value.length === 0) {
        qaPairs.value = [{ question: '', answer: '' }]
      }
    }
  } catch {
    ElMessage.error('加载反馈详情失败')
  } finally {
    loadingDetail.value = false
  }
}
```

> 📌 **为何预计算而不是在模板里直接写 `v-html="renderMarkdown(msg.content)"`**：拖拽分隔条会频繁修改 `resizerWidth`，导致整个组件重渲染；若渲染表达式写在模板中，每次 patch 都会重新执行 `marked.parse()`。预计算后只在详情数据到达时解析一次，拖拽时仅复用缓存字符串。

> 📌 **为何不复用 `syncDerived()`**：`messageUtils.ts:39` 的 `syncDerived()` 还包含流式节流、`steps` / `reasoning` 清洗等与本页无关的逻辑，且其 `UIMessage.role` 类型为 `'user' | 'assistant'`，本页 `role: string` 需强转。本页只需纯渲染函数，故直接调用 `renderMarkdown()`。

#### 4.1.6 关键代码 — 模板部分（`FeedbackTab.vue:298`）

```html
<div class="chat-bubble-wrapper">
  <div
    class="chat-bubble"
    :class="{
      'chat-bubble--user': msg.role === 'user',
      'chat-bubble--ai': msg.role !== 'user',
    }"
    v-html="msg._renderedHtml ?? ''"   <!-- 【改造】原为 {{ msg.content }} -->
  ></div>
  <button
    class="chat-msg-copy-btn"
    @click="copyMessage(msg.content)"  <!-- 【无改动】复制原始 Markdown -->
    title="复制"
  >
    📋
  </button>
</div>
```

> ⚠️ `v-html` 节点由运行时插入，**不会带 scoped 属性**，因此样式必须写在 `:deep()` 中（见 4.1.7）。

#### 4.1.7 CSS 关键样式（追加到 `<style scoped>`，位于现有 `.chat-bubble` 规则之后）

基线样式来源：`frontend/src/views/admin/AgentConfigTab.vue:254` 的 `.markdown-body`，按气泡尺寸缩小字号与间距，并补充用户蓝底气泡的反色覆盖。

```css
/* ── Markdown 渲染内容（仅在对话气泡内生效） ── */
.chat-bubble :deep(h1),
.chat-bubble :deep(h2),
.chat-bubble :deep(h3) { font-weight: 600; margin: 6px 0 4px; }
.chat-bubble :deep(h1) { font-size: 17px; }
.chat-bubble :deep(h2) { font-size: 15px; }
.chat-bubble :deep(h3) { font-size: 14px; }
.chat-bubble :deep(p) { margin: 4px 0; }
.chat-bubble :deep(p:first-child) { margin-top: 0; }
.chat-bubble :deep(p:last-child) { margin-bottom: 0; }
.chat-bubble :deep(ul),
.chat-bubble :deep(ol) { padding-left: 18px; margin: 4px 0; }
.chat-bubble :deep(li) { margin: 2px 0; }
.chat-bubble :deep(code) {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  padding: 1px 4px;
  border-radius: var(--radius-sm);
  font-size: 12px;
}
.chat-bubble :deep(pre) {
  background: var(--color-bg-page);
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  margin: 6px 0;
}
.chat-bubble :deep(pre code) { background: none; padding: 0; }
.chat-bubble :deep(blockquote) {
  border-left: 3px solid var(--color-border);
  padding-left: 8px;
  margin: 6px 0;
  color: var(--color-text-secondary);
}
.chat-bubble :deep(a) { color: var(--color-primary); }
.chat-bubble :deep(table) { border-collapse: collapse; width: 100%; margin: 6px 0; }
.chat-bubble :deep(th),
.chat-bubble :deep(td) {
  border: 1px solid var(--color-border);
  padding: 4px 6px;
  text-align: left;
}
.chat-bubble :deep(th) { background: var(--color-bg-page); font-weight: 600; }
.chat-bubble :deep(img) { max-width: 100%; height: auto; }

/* ── 用户气泡为蓝底白字，覆盖为浅色前景以保证可读 ── */
.chat-bubble--user :deep(a) { color: var(--color-bg-card); text-decoration: underline; }
.chat-bubble--user :deep(code),
.chat-bubble--user :deep(pre),
.chat-bubble--user :deep(th) {
  background: color-mix(in srgb, var(--color-bg-card) 18%, transparent);
  color: var(--color-bg-card);
}
.chat-bubble--user :deep(pre code) { background: none; }
.chat-bubble--user :deep(blockquote) {
  border-left-color: color-mix(in srgb, var(--color-bg-card) 60%, transparent);
  color: var(--color-bg-card);
}
.chat-bubble--user :deep(th),
.chat-bubble--user :deep(td) {
  border-color: color-mix(in srgb, var(--color-bg-card) 40%, transparent);
}
```

| 区域 | 样式说明 |
|------|---------|
| 消息气泡内 Markdown | 标题/段落/列表/代码/引用/表格/图片，字号与间距小于配置预览（13px 气泡基线），避免撑破 `max-width: 70%` |
| 用户蓝底气泡 | 链接、代码、引用、表格边框反色为白系；全部由 `var(--color-bg-card)` 派生，不引入新色值 |
| 作用域隔离 | 所有规则以 `.chat-bubble` 为前缀，不影响左侧列表、改写区、`AgentConfigTab.vue` 预览 |

> ⚠️ 现有 `.chat-bubble--user { color: #fff }` 保持不动；新增覆盖仅处理 Markdown 生成的子元素。

---

## 五、前后端交互完整流程

### 5.1 选中反馈 → 详情加载 → Markdown 渲染（主场景）

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    不满意回答预览 Markdown 渲染完整时序                    │
│                                                                          │
│  前端 (FeedbackTab.vue)    前端 API 层          后端 (FastAPI)             │
│  ──────────────────────    ──────────────        ──────────────             │
│                                                                          │
│  1. 管理员点击左侧反馈条目                                                 │
│  2. selectedFeedbackId = fb.id；messages = []（防止残留）                  │
│  3. ── getFeedbackDetail(fb.id) ─────▶ adminAuthFetch                    │
│  4.                              ── GET /api/admin/feedbacks/{id} ──▶     │
│  5.                                        6. 查 feedback + messages      │
│  7.                              ◀── {ok:true, data:{messages:[原始md]}} ─ │
│  8. ◀── Response ───────────────                                          │
│  9. messages = data.messages.map(m => ({...m,                            │
│        _renderedHtml: renderMarkdown(m.content)}))   ← 一次性解析           │
│ 10. v-html 插入 → 气泡显示为标题/加粗/列表/代码块/表格                       │
│ 11. qaPairs 由 data.messages 原文生成（与渲染结果无关）                      │
│ 12. loadingDetail = false                                                │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.2 复制原文（回归场景）

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              复制原始 Markdown 时序                       │
│                                                                          │
│  1. 鼠标 hover 消息行 → .chat-msg-copy-btn opacity: 0 → 1                 │
│  2. 点击 📋 → copyMessage(msg.content)                                    │
│  3. navigator.clipboard.writeText(content)                               │
│     content 形如 "## 退款流程\n**步骤 1**：提交申请"（含 Markdown 标记）      │
│  4. ElMessage.success('已复制到剪贴板')                                   │
│                                                                          │
│  ✅ 全链路不读取 _renderedHtml；粘贴到改写 Q/A 框的内容与改造前完全一致       │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.3 切换反馈 / 筛选变化（状态清理场景）

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            切换与清理时序                                  │
│                                                                          │
│  A. 选中另一条反馈：selectFeedback() 先 messages=[] → 再拉详情 → 重建缓存    │
│  B. 修改筛选：onFilterChange() → selectedFeedbackId=null / messages=[]     │
│     / qaPairs 重置 → 右侧详情面板 v-if 为 false，整块卸载                   │
│  C. 完成处理：handleResolve() → messages=[] / selectedFeedbackId=null      │
│                                                                          │
│  结论：任何入口都先清空再赋值，_renderedHtml 随消息对象一起被丢弃，不会串页   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 六、技术架构依赖清单

### 6.1 前端新增依赖

**无需新增**。`marked@^18.0.4` 已在 `frontend/package.json:13`，`renderMarkdown()` 已在 `frontend/src/components/messageUtils.ts:32` 封装完毕。

### 6.2 后端新增依赖

**无需新增**。后端零改动。

### 6.3 新增文件清单

| 文件路径 | 说明 | 优先级 |
|---------|------|:--:|
| `docs/prd/08_不满意回答对话预览Markdown渲染.md` | 需求文档（已产出） | 🟡 中 |
| `docs/dev_docs/08_不满意回答对话预览Markdown渲染.md` | 本文档 | 🟡 中 |

> 本次**无新增源码文件**。

### 6.4 改造现有文件清单

| 文件路径 | 改造内容 | 优先级 |
|---------|---------|:--:|
| `frontend/src/views/admin/FeedbackTab.vue` | 导入 `renderMarkdown`；`Message` 增字段；详情赋值时生成 `_renderedHtml`；消息气泡改 `v-html`；追加 Markdown 排版样式 | 🔴 高 |
| `frontend/src/components/messageUtils.ts` | **无改动**，仅复用 `renderMarkdown()` | ❌ 无需 |
| `frontend/src/views/admin/AgentConfigTab.vue` | **无改动**，仅作为 `.markdown-body` 样式参考来源 | ❌ 无需 |
| `frontend/src/api/admin.ts` | **无改动** | ❌ 无需 |
| `backend/routers/feedback.py` | **无改动** | ❌ 无需 |
| `docs/prd/03_管理员后台页.md` | 建议按 PRD 08 第八章回写 §六 6.1 ⑦.2 / 6.6 | 🔵 低 |

### 6.5 环境变量新增

**无**。

---

## 七、状态管理与全局配置

### 7.1 前端状态：新增缓存字段而非新 Store

本次不引入 Pinia / composable 级新状态，仅在既有 `messages` ref 的每条消息上追加渲染缓存，遵循项目已有的 `UIMessage._renderedHtml` 约定（`frontend/src/components/messageUtils.ts:13`）。

```typescript
// frontend/src/views/admin/FeedbackTab.vue
interface Message {
  id: number
  role: string
  content: string                 // 原始 Markdown：复制、Q&A 生成的唯一数据源
  reasoning_content: string
  created_at: number
  _renderedHtml?: string          // 展示用 HTML 缓存：仅 v-html 读取
}
```

| 状态 | 生命周期 | 说明 |
|------|---------|------|
| `messages` | 组件内 `ref<Message[]>` | 选中反馈时重建；筛选变化/处理完成时清空 |
| `_renderedHtml` | 随消息对象创建与销毁 | 详情到达时一次性生成；不持久化、不回写后端 |
| `resizerWidth` | 组件内 `ref<number>` | 拖拽时变化，但只影响 flex 宽度，**不再触发 Markdown 重解析** |

### 7.2 复用的渲染函数（来自 `frontend/src/components/messageUtils.ts:16-34`）

```typescript
const renderer = new marked.Renderer()
renderer.image = function (token: any): string {
  let href = typeof token === 'string' ? token : (token?.href || '')
  if (href.startsWith('../assets/')) href = href.replace(/^\.\.\//, '/')  // 图片路径改写
  // ... 流式占位逻辑（_streaming=false 时不生效）
}
marked.setOptions({ breaks: true, gfm: true, renderer })

export function renderMarkdown(text: string): string {
  try { return marked.parse(text || '') as string } catch { return text || '' }
}
```

要点（PRD R1~R5）：

- `breaks: true`：单换行转 `<br>`；
- `gfm: true`：表格、删除线、任务列表等生效；
- `../assets/xxx` → `/assets/xxx`：知识库图片可在后台正常加载；
- `try/catch`：解析异常自动回退原文；
- **流式占位不生效**：`_streaming` 默认 `false`，本页不调用 `setStreamingRender(true)`，图片直接输出 `<img>`。

### 7.3 CSS 变量注入（沿用现有 `frontend/src/style.css`）

本次新增样式只使用既有变量，不硬编码新色值：

| 变量 | 用途 | 现有值 |
|------|------|--------|
| `--color-primary` | AI 气泡链接色 | `#2B67FF` |
| `--color-text-primary` | 代码/正文前景 | `#212633` |
| `--color-text-secondary` | 引用文字 | `#465164` |
| `--color-border` | 表格边框、引用左侧线 | `#DEE0E3` |
| `--color-border-light` | （沿用气泡边框，未新增） | `#EAECF1` |
| `--color-bg-page` | 代码块 / 表头背景 | `#F0F2F7` |
| `--color-bg-card` | 用户气泡反色前景（`color-mix` 派生半透明） | `#FFFFFF` |
| `--radius-sm` / `--radius-md` | 代码块圆角 | `4px` / `8px` |

> UI 框架主题覆盖：本次不涉及 Element Plus 主题变量修改。

---

## 八、部署与构建说明（沿用现有）

### 8.1 开发环境

```bash
# 后端（backend/ 目录）
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 前端（frontend/ 目录）
npm install
npm run dev
```

### 8.2 生产构建

```bash
cd frontend && npm run build
```

> `npm run build` 会先执行 `vue-tsc -b`：`Message` 新增的可选字段与 `v-html` 写法须通过类型检查（字段已声明为可选，不会破坏既有赋值）。

### 8.3 数据库迁移

**无**。本次无表结构变更，无数据回填。

### 8.4 部署注意

- 纯前端改动，后端无需重新发布（如需同步发版亦可）；
- 确认 `marked` 已在生产依赖中（非 devDependency），当前 `package.json` 满足；
- `color-mix()` 需现代浏览器（Chrome 111+ / Safari 16.2+ / Firefox 113+）；管理后台面向内部人员，按现状可接受。如需兼容旧浏览器，将用户气泡覆盖改为由 `--color-bg-card` 派生的预定义 RGBA 变量即可。

---

## 九、开发顺序建议

| 阶段 | 任务 | 优先级 | 依赖 |
|:--:|------|:--:|------|
| 1 | `FeedbackTab.vue` 导入 `renderMarkdown`，`Message` 接口新增 `_renderedHtml` | 🔴 高 | — |
| 2 | `selectFeedback()` 中 `map()` 生成渲染缓存，确认 `qaPairs` 仍用原文 | 🔴 高 | 1 |
| 3 | 消息气泡改为 `v-html`，复制按钮保持读取 `msg.content` | 🔴 高 | 2 |
| 4 | 追加 `.chat-bubble :deep(...)` 排版样式 + 用户气泡反色覆盖 | 🔴 高 | 3 |
| 5 | 按第十一节验收清单逐条走查（含代码块/表格/图片、复制原文、切换、拖拽） | 🟡 中 | 4 |
| 6 | 按 PRD 08 第八章回写 `docs/prd/03_管理员后台页.md` §六 6.1 / 6.6 | 🔵 低 | 5 |

---

## 十、补充考量

### 10.1 错误处理与边界情况

| 场景 | 前端处理 | 后端处理 |
|------|---------|---------|
| `content` 为空 / 空白 | `renderMarkdown('')` → `''`，气泡空占位、无报错 | 原样返回空串 |
| `content` 为纯文本（无 Markdown 语法） | `marked` 输出 `<p>文本</p>`，视觉与改造前基本一致（段落上下间距由样式压到 4px） | 无 |
| `content` 含 HTML 标签 | `marked` 按 GFM 规则透传，与用户端一致；不做额外净化（PRD N1） | 无 |
| `content` 含 `../assets/` 图片 | renderer 改写为 `/assets/` 后加载；失效时保留浏览器默认破图 | 无 |
| `content` 含数学公式 `$...$` | 不引入 KaTeX，按普通文本处理（PRD 六） | 无 |
| `marked.parse()` 抛错 | `renderMarkdown()` 内部 `catch` 返回原文 | 无 |
| 详情接口 404 / 网络失败 | 沿用现有 `ElMessage.error('加载反馈详情失败')`，`messages` 保持空 | 沿用现有 |
| 快速连续切换反馈 | `selectFeedback()` 先清空 `messages`；渲染缓存随新对象重建，不串页 | 无 |
| 拖拽分隔条频繁重渲染 | 只读缓存字符串，不重复 `marked.parse()` | 无 |
| Token 过期 | `adminAuthFetch()` 统一清除 `admin_token` 并跳转 `/admin/login` | 401 |

### 10.2 安全性关注点

| 关注点 | 措施 |
|--------|------|
| XSS（本次主要风险） | ⚠️ 已知风险：`v-html` 无净化，与用户端 `AgentChatMessages.vue:96`、维护助手 `MaintenanceChatDialog.vue:93`、配置预览 `AgentConfigTab.vue:135` 保持一致（PRD N1）。内容来源为本系统已认证用户与 LLM，管理端仅管理员可见。统一净化方案列入后续评估，不单页引入以免行为分叉 |
| 越权访问 | 沿用 `get_current_user` / `require_admin` 与 `adminAuthFetch()`，无新增接口 |
| SQL 注入 | 无新增 SQL；后端详情查询使用参数化查询（`feedback.py:129`、`:141`） |
| 敏感信息保护 | 无新增日志；`content` 只在内存中解析，不写入新存储 |
| Token 存储 | 沿用 `localStorage.admin_token`，无改动 |

### 10.3 性能考量

| 场景 | 措施 |
|------|------|
| 消息渲染 | 详情到达时一次性 `map()` 渲染；`v-html` 只读缓存，避免拖拽/筛选导致的重复解析 |
| 大对话量 | 单条反馈消息数有限（列表按消息条数展示）；无分页需求，渲染开销随详情加载一次性发生 |
| 图片 | `marked` 生成的 `<img>` 由浏览器按需加载；`max-width: 100%` 防止撑破气泡 |
| API 请求 | **零新增请求**，完全复用详情接口返回的 `content` |

### 10.4 兼容性规划

| 项目 | 说明 |
|------|------|
| 数据兼容 | 旧消息 `content` 本就是 Markdown 原文，改造后无需回填；纯文本消息渲染后视觉基本一致 |
| API 向后兼容 | 接口契约完全不变；前端新增的是可选本地字段 `_renderedHtml`，不影响其他消费方 |
| 复制行为兼容 | 剪贴板内容与改造前逐字节一致（回归项 AC3） |
| 浏览器兼容 | `color-mix()` 需现代浏览器；降级方案见 8.4 |
| 与其他预览页的关系 | 不改动 `AgentConfigTab.vue` 的 `.markdown-body` 样式，保持独立作用域 |

### 10.5 测试策略

| 测试类型 | 范围 | 要点 |
|---------|------|------|
| 前端功能（手工） | 构造含标题/加粗/列表/代码块/表格/图片的 AI 回复 | 气泡显示为富文本，无原始标记符号 |
| 前端功能（手工） | 用户消息含 Markdown | 同样渲染；蓝底气泡内链接/代码可读 |
| 回归（手工） | 点击 📋 → 粘贴到任意纯文本编辑器 | 得到原始 Markdown（含 `#`、`**`、换行） |
| 回归（手工） | 切换反馈、筛选、拖拽分隔条、改写增删、完成处理 | 行为与改造前一致；无串页 |
| 类型检查 | `npm run build` | `vue-tsc -b` 通过 |
| 控制台检查 | 打开详情 + 切换 + 拖拽全过程 | 无 Vue 警告 / JS 异常 |

### 10.6 开发规范

- **命名规范**：Vue 组件 `PascalCase`，缓存字段沿用 `_renderedHtml`（与 `UIMessage` 一致）；
- **注释规范**：`_renderedHtml` 字段与 `map()` 处需注释「仅展示用，复制/Q&A 仍读 `content`」；
- **Git 提交规范**：`feat: 不满意回答预览区 Markdown 渲染`；
- **类型安全**：`Message._renderedHtml` 声明为可选，`v-html` 用 `?? ''` 兜底，禁止 `any` 断言扩散；`renderMarkdown` 入参来自接口 `string`，无需额外断言。

---

## 十一、验收清单

对应 PRD 08 第九章 AC1~AC9：

- [ ] **AC1** 打开含 `# 标题`、`**加粗**`、`- 列表`、代码块、表格、图片链接的 AI 回复，预览区显示排版后的富文本，无原始标记符号
- [ ] **AC2** 用户消息中的 Markdown 同样被渲染；蓝底气泡内链接、代码、引用、表格文字清晰可读
- [ ] **AC3** 点击任意消息 📋，剪贴板内容与接口返回 `content` 完全一致（含 `#`、`**`、换行），可原样粘贴到改写 Q/A 框
- [ ] **AC4** 单换行按 `<br>` 展示，GFM 表格正常成表，与用户端客服对话页表现一致
- [ ] **AC5** `../assets/` 开头的图片在预览区正常加载
- [ ] **AC6** 依次切换多条反馈详情，渲染结果正确，无上一条对话内容或样式残留
- [ ] **AC7** 空内容、纯文本、含原始 HTML 的内容均不导致空白页、报错或控制台异常
- [ ] **AC8** 筛选、日期分组展开/收起、拖拽分隔条、改写 Q&A 增删、完成处理与 FAQ 写入流程均不受影响
- [ ] **AC9** 改写输入区 Q / A 仍为纯文本编辑，不出现渲染后的 HTML
- [ ] `npm run build` 通过（`vue-tsc` 无类型错误）

---

## 十二、需求追踪矩阵

| 需求编号（PRD 08） | 需求摘要 | 实现位置 | 验收项 |
|-------------------|---------|---------|--------|
| G1 | 消息区 Markdown 渲染（用户 + AI） | `FeedbackTab.vue` 模板 `v-html` + `map()` 预计算 | AC1、AC2 |
| G2 | 与用户端渲染效果一致 | 复用 `messageUtils.ts:renderMarkdown()` 与 `marked` 全局配置 | AC4、AC5 |
| G3 | 复制仍为原始 Markdown | `copyMessage(msg.content)` 保持不变；`qaPairs` 读原文 | AC3、AC9 |
| G4 | 纯前端改造，不改后端/存储 | 第三章无接口变更；第六章无后端文件改动 | AC8 |
| R1~R3 | 复用渲染函数 / `breaks`+`gfm` / 图片路径 | `renderMarkdown()` + `renderer.image` | AC1、AC4、AC5 |
| R4~R5 | 空值兜底 / 异常兜底 | `renderMarkdown()` 内 `text || ''` 与 `try/catch` | AC7 |
| R6 | 渲染只影响展示层 | `_renderedHtml` 仅 `v-html` 读取；`content` 不变 | AC3 |
| R7 | 样式限定在气泡内 | `.chat-bubble :deep(...)` 作用域规则 | AC2、AC8 |
| N1 | 不做 HTML 净化 | 10.2 安全性关注点，统一治理列入后续评估 | AC7 |
| N2~N6 | 不渲染推理/附件、不动输入区、无流式、无新依赖、不改后端 | 第六章依赖清单 + 4.1.4 改造清单 | AC8、AC9 |
| 6.6 / §六修订 | 回写原 PRD | `docs/prd/03_管理员后台页.md` §六 6.1 ⑦.2、6.6 | 阶段 6 |
