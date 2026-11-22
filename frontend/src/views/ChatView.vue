<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { marked } from 'marked'
import {
  listSessions,
  getSessionMessages,
  createSession,
  streamChat,
  deleteSession as apiDeleteSession,
  updateSessionTitle as apiUpdateSessionTitle,
  submitFeedback,
  checkFeedback,
} from '../api/chat'
import type { AttachmentPayload, ChatAttachment, ChatMessage, Session } from '../api/chat'
import { getAttachmentContent } from '../api/attachments'
import { useAuth } from '../composables/useAuth'
import { useSessionRuntimes } from '../composables/useSessionRuntimes'
import ChatInput from '../components/ChatInput.vue'
import AttachmentCard from '../components/AttachmentCard.vue'

const { currentUser, logout } = useAuth()

// ==================== DEBUG 开关 ====================
// 与 api/chat.ts 保持一致：逐 token 日志默认关闭。
// 开启方式：控制台执行 localStorage.setItem('chat_debug', '1') 后刷新页面。
function readDebugFlag(): boolean {
  try {
    return localStorage.getItem('chat_debug') === '1'
  } catch {
    return false
  }
}
const DEBUG_STREAM = import.meta.env.DEV && readDebugFlag()

// ==================== 侧边栏状态 ====================
const sessions = ref<Session[]>([])
const searchKeyword = ref('')
const loadingMore = ref(false)
const hasMoreSessions = ref(false)
const sessionsOffset = ref(0)
const SESSIONS_LIMIT = 10

const filteredSessions = computed(() => {
  const list = sessions.value || []
  if (!searchKeyword.value.trim()) return list
  const kw = searchKeyword.value.toLowerCase()
  return list.filter(s => (s.title || '新对话').toLowerCase().includes(kw))
})

// 侧边栏拖拽
const sidebarWidth = ref(260)
const isDragging = ref(false)
let dragStartX = 0
let dragStartWidth = 0

function onResizerMouseDown(e: MouseEvent) {
  isDragging.value = true
  dragStartX = e.clientX
  dragStartWidth = sidebarWidth.value
  document.addEventListener('mousemove', onResizerMouseMove)
  document.addEventListener('mouseup', onResizerMouseUp)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onResizerMouseMove(e: MouseEvent) {
  if (!isDragging.value) return
  let newWidth = dragStartWidth + (e.clientX - dragStartX)
  newWidth = Math.max(200, Math.min(500, newWidth))
  const mainMin = 400
  if (window.innerWidth - newWidth < mainMin) {
    newWidth = window.innerWidth - mainMin
  }
  sidebarWidth.value = newWidth
}

function onResizerMouseUp() {
  isDragging.value = false
  document.removeEventListener('mousemove', onResizerMouseMove)
  document.removeEventListener('mouseup', onResizerMouseUp)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// ==================== 对话状态 ====================
const currentSessionId = ref('')
const loadingMessages = ref(false)
const hasMoreMessages = ref(false)

const currentTitle = computed(() => {
  const s = (sessions.value || []).find(s => s.id === currentSessionId.value)
  return s?.title || '新对话'
})

// ==================== 编辑状态 ====================
const editingSessionId = ref('')
const editingTitle = ref('')
const editingTitleInTop = ref(false)
const titleInputValue = ref('')

// ==================== 滚动状态 ====================
const messageArea = ref<HTMLElement>()
const userAtBottom = ref(true)
const sidebarList = ref<HTMLElement>()

// ==================== 反馈状态 ====================
const hasFeedback = ref(false)

// ==================== 图片预览状态 ====================
const previewImage = ref<string | null>(null)
let previewBlobUrl: string | null = null

// ==================== 类型 ====================
interface RetrievalImage {
  alt: string
  path: string
  source?: string
}

interface TaskInfo {
  type: string
  result: string
  /** 检索词（仅 knowledge_retrieval） */
  query?: string
  /** 从 result 拆出的命中文本，保留原始换行 */
  hitText?: string
  /** 从 result 拆出的命中图片 */
  images?: RetrievalImage[]
}

/** 思考过程的时间线节点，与后端 _StepBuilder 落库的 steps 一一对应 */
interface ThinkingStep {
  kind: 'reasoning' | 'task'
  /** reasoning 片段原文（连续 token 已合并） */
  text?: string
  /** 清洗后的缓存，随节流渲染更新，避免模板对每个 token 重跑全文正则 */
  clean?: string
  /** task 节点的结构化结果 */
  task?: TaskInfo
}

interface UIMessage {
  id?: number
  role: 'user' | 'assistant'
  content: string
  /** 用户上传的图片/PDF；previewUrl 用于发送后即时预览 */
  attachments?: (ChatAttachment & { previewUrl?: string })[]
  /** 整段思维链，仅用于「是否有思考过程」判定与兼容，渲染以 steps 为准 */
  reasoning?: string
  steps?: ThinkingStep[]
  showThinking?: boolean
  isStreaming?: boolean
  showRegenerate?: boolean
  error?: string
  created_at?: number
  /** 节流后的 markdown 渲染 HTML，流式期间每 150ms 更新一次，防止图片闪动 */
  _renderedHtml?: string
  /** 下一个 reasoning token 是否另起节点，与后端 _StepBuilder.break_reasoning 同构 */
  _stepBreak?: boolean
}

// ==================== 会话运行时（按会话隔离生成状态） ====================
const {
  runtimes,
  ensureRuntime,
  isActiveCallback,
  markGenerating,
  finishGenerating,
  markUnread,
  markRead,
  disposeRuntime,
  disposeAllRuntimes,
  isSessionGenerating,
} = useSessionRuntimes<UIMessage>()

const currentRuntime = computed(() =>
  currentSessionId.value ? ensureRuntime(currentSessionId.value) : undefined,
)
/** 当前会话是否正在生成；输入框 / 停止按钮 / 顶部徽标都以此为准 */
const isCurrentStreaming = computed(() => !!currentRuntime.value?.generating)
/** 视图只渲染当前会话的缓存（含流式半成品） */
const currentMessages = computed<UIMessage[]>(() => currentRuntime.value?.messages || [])
/** 文本草稿按会话隔离：切换会话互不干扰，停止后保留 */
const currentDraft = computed({
  get: () => currentRuntime.value?.draft || '',
  set: (v: string) => { if (currentRuntime.value) currentRuntime.value.draft = v },
})

// ==================== 工具函数 ====================

// 流式渲染期间不产出 <img>：_renderedHtml 每 150ms 被整体替换（v-html 是全量重建），
// 若期间渲染出图片，每个 <img> 每 150ms 就被销毁重建一次、重新发起请求
// （实测同一次回答中同一张图被重复请求数十次）。
// 流式结束后（isStreaming=false）再完整渲染，此时每张图只请求一次。
let _streamingRender = false

// 自定义 marked 渲染器：将相对路径的图片 src 转为服务端绝对路径
const markedRenderer = new marked.Renderer()
const originalImageRenderer = markedRenderer.image.bind(markedRenderer)
markedRenderer.image = function (token: any): string {
  const href: string = token.href
  // ../assets/xxx → /assets/xxx  （兜底修正，防止 LLM 输出的相对路径图片显示为裂图）
  if (href.startsWith('../assets/') || href.includes('/../assets/')) {
    token.href = href.replace(/(?:\.\.\/)+assets\//g, '/assets/')
  }
  if (_streamingRender) {
    // 流式期间用占位文本代替图片，避免反复重建 <img>
    return `<span class="img-stream-placeholder">[图片${token.text ? '：' + token.text : ''}]</span>`
  }
  return originalImageRenderer(token)
}

marked.setOptions({ breaks: true, gfm: true, renderer: markedRenderer })

function renderMarkdown(text: string): string {
  if (!text) return ''
  return marked.parse(text) as string
}

/** 流式渲染节流：防止图片等 DOM 元素频繁重建导致闪动 */
const RENDER_THROTTLE_MS = 150
const _renderTimers = new WeakMap<object, ReturnType<typeof setTimeout>>()

function syncDerived(msg: UIMessage) {
  // 流式期间禁用图片渲染，避免每 150ms 重建 <img> 导致图片被反复请求
  _streamingRender = !!msg.isStreaming
  try {
    msg._renderedHtml = renderMarkdown(msg.content)
  } finally {
    _streamingRender = false
  }
  // 各 reasoning 步骤的清洗（两次全文正则 + trim）一并节流：
  // 否则模板会在每个 token 上对全文重算，整体复杂度 O(n²)
  for (const step of msg.steps || []) {
    if (step.kind === 'reasoning') step.clean = cleanReasoning(step.text || '')
  }
}

function scheduleRender(msg: UIMessage) {
  if (!msg.isStreaming) {
    // 非流式（已完成/历史消息/出错）：立即渲染
    syncDerived(msg)
    return
  }

  // 流式期间：已有待执行的定时器则跳过，避免反复重置导致永不触发
  if (_renderTimers.has(msg)) return

  _renderTimers.set(msg, setTimeout(() => {
    _renderTimers.delete(msg)
    syncDerived(msg)
  }, RENDER_THROTTLE_MS))
}

function cleanReasoning(text: string): string {
  return text.replace(/<\/?think>/gi, '').replace(/<THINK_V2>/gi, '').trim()
}

// ==================== knowledge_retrieval 结果解析 ====================
// format_knowledge_retrieval_result 的输出固定为：
//   ### 命中文本
//   ...
//   ### 命中图片（可选）
//   使用 ![图片说明](图片路径) 的 markdown 格式展示图片，例如：
//   - ![alt](/assets/xxx.png)
//     source: context/xxx.md
// 拆开后可保留命中文本原始换行，并把图片单独列出；解析失败时整体作为正文，保证不丢内容。
const RETRIEVAL_IMAGE_MARK = '### 命中图片（可选）'
const RETRIEVAL_IMAGE_RE = /^\s*-\s*!\[([^\]]*)\]\(([^)]+)\)/
const RETRIEVAL_SOURCE_RE = /^\s*source:\s*(.+)$/

function parseRetrievalResult(result: string): { hitText: string; images: RetrievalImage[] } {
  const markIndex = result.indexOf(RETRIEVAL_IMAGE_MARK)
  const textPart = markIndex >= 0 ? result.slice(0, markIndex) : result
  const imagePart = markIndex >= 0 ? result.slice(markIndex + RETRIEVAL_IMAGE_MARK.length) : ''
  const hitText = textPart.replace(/^###\s*命中文本\s*/, '').trim()
    || result.trim()
    || '（未命中）'

  const images: RetrievalImage[] = []
  const lines = imagePart.split('\n')
  for (let i = 0; i < lines.length; i++) {
    const matched = lines[i].match(RETRIEVAL_IMAGE_RE)
    if (!matched) continue
    const sourceMatched = (lines[i + 1] || '').match(RETRIEVAL_SOURCE_RE)
    images.push({
      alt: matched[1] || '检索图片',
      path: matched[2],
      source: sourceMatched ? sourceMatched[1].trim() : '',
    })
  }
  return { hitText, images }
}

function makeTask(type: string, result: string, query = ''): TaskInfo {
  const task: TaskInfo = { type, result, query }
  if (type === 'knowledge_retrieval') {
    const parsed = parseRetrievalResult(result)
    task.hitText = parsed.hitText
    task.images = parsed.images
  }
  return task
}

// ==================== 思考过程步骤时间线 ====================
// 与后端 _StepBuilder 同构：连续 reasoning token 合并、遇 content / task 断开。
// 这样流式期间构造的 steps 与落库回放的 steps 完全一致，刷新后顺序不变。
const THINK_MARKER_RE = /<THINK_V2>|<\/?think>/gi

function appendReasoningStep(msg: UIMessage, text: string) {
  // <THINK_V2> / <think> / </think> 是后端合成的控制帧，落库序列里不存在
  const cleaned = text.replace(THINK_MARKER_RE, '')
  if (!cleaned) return
  const steps = msg.steps || (msg.steps = [])
  const last = steps[steps.length - 1]
  if (!msg._stepBreak && last && last.kind === 'reasoning') {
    last.text = (last.text || '') + cleaned
  } else {
    steps.push({ kind: 'reasoning', text: cleaned, clean: cleaned })
  }
  msg._stepBreak = false
}

function breakReasoningStep(msg: UIMessage) {
  msg._stepBreak = true
}

function appendTaskStep(msg: UIMessage, type: string, result: string, query: string) {
  const steps = msg.steps || (msg.steps = [])
  steps.push({ kind: 'task', task: makeTask(type, result, query) })
  msg._stepBreak = true
}

/** 历史消息：新数据直接回放 steps；旧数据回退为「整段思维链 + 任务列表」 */
function buildHistorySteps(m: ChatMessage): ThinkingStep[] {
  if (m.steps && m.steps.length > 0) {
    return m.steps.map<ThinkingStep>(s => s.kind === 'task'
      ? { kind: 'task', task: makeTask(s.type || '', s.result || '', s.query) }
      : { kind: 'reasoning', text: s.text || '', clean: cleanReasoning(s.text || '') })
  }
  const steps: ThinkingStep[] = []
  if (m.reasoning_content) {
    steps.push({
      kind: 'reasoning',
      text: m.reasoning_content,
      clean: cleanReasoning(m.reasoning_content),
    })
  }
  for (const t of m.tasks || []) {
    steps.push({ kind: 'task', task: makeTask(t.type, t.result, t.query) })
  }
  return steps
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  const y = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const da = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${mo}-${da} ${h}:${mi}`
}

function formatMessageTime(ts: number): string {
  const d = new Date(ts * 1000)
  const h = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${h}:${mi}:${s}`
}

function showTimeDivider(msg: UIMessage, i: number): boolean {
  if (i === 0) return true
  const prev = currentMessages.value[i - 1]
  if (!msg.created_at || !prev.created_at) return false
  return (msg.created_at - prev.created_at) > 300
}

function truncatePreview(text: string | undefined): string {
  if (!text) return ''
  return text.length > 50 ? text.slice(0, 50) + '...' : text
}

function isVisibleMessage(m: { role: string; content: string }): boolean {
  if (m.role === 'assistant') return true
  if (m.role !== 'user') return false
  return !m.content.startsWith('<task_result>')
}

// ==================== 数据加载 ====================
async function loadSessions() {
  try {
    const res = await listSessions(SESSIONS_LIMIT, 0)
    sessions.value = res.sessions || []
    hasMoreSessions.value = res.has_more
    sessionsOffset.value = sessions.value.length
  } catch {
    // handled by authFetch interceptor
  }
}

async function loadMoreSessions() {
  if (loadingMore.value || !hasMoreSessions.value) return
  loadingMore.value = true
  try {
    const res = await listSessions(SESSIONS_LIMIT, sessionsOffset.value)
    sessions.value.push(...(res.sessions || []))
    hasMoreSessions.value = res.has_more
    sessionsOffset.value += (res.sessions || []).length
  } catch {
    // handled by authFetch
  }
  loadingMore.value = false
}

async function loadMessages(sessionId: string) {
  loadingMessages.value = true
  const rt = ensureRuntime(sessionId)
  try {
    const res = await getSessionMessages(sessionId)
    const visible = res.messages.filter(isVisibleMessage)
    rt.messages = visible.map((m) => ({
      id: m.id,
      role: m.role as 'user' | 'assistant',
      content: m.content,
      attachments: m.attachments || [],
      reasoning: m.reasoning_content || '',
      steps: buildHistorySteps(m),
      showThinking: !!(m.reasoning_content || m.steps?.length || m.tasks?.length),
      isStreaming: false,
      created_at: m.created_at,
    }))
    hasMoreMessages.value = res.has_more
  } catch {
    rt.messages = []
  }
  loadingMessages.value = false
}

async function loadFeedbackStatus(sessionId: string) {
  try {
    const res = await checkFeedback(sessionId)
    hasFeedback.value = res.has_feedback
  } catch {
    hasFeedback.value = false
  }
}

// ==================== 对话操作 ====================
function saveViewState(sid: string) {
  const rt = runtimes[sid]
  if (rt) rt.scrollTop = messageArea.value?.scrollTop || 0
}

function restoreViewState(sid: string) {
  const rt = runtimes[sid]
  if (rt && messageArea.value) messageArea.value.scrollTop = rt.scrollTop
}

async function handleSelectSession(sid: string) {
  if (sid === currentSessionId.value) return
  if (currentSessionId.value) saveViewState(currentSessionId.value)

  currentSessionId.value = sid
  // 切换到该对话即视为已读，清除未读标识
  markRead(sid)
  const rt = ensureRuntime(sid)
  const wasInitialized = rt.initialized

  // 生成中的会话使用本地缓存，跳过 loadMessages，避免数据库内容覆盖流式半成品
  if (!rt.initialized) {
    await loadMessages(sid)
    rt.initialized = true
  }
  await loadFeedbackStatus(sid)
  _thinkingContentEl = null
  await nextTick()
  if (wasInitialized) restoreViewState(sid)
  else scrollToBottom()
}

async function handleNewChat() {
  try {
    const sid = await createSession()
    if (!sid) return
    ensureRuntime(sid)
    await loadSessions()
    if (currentSessionId.value) saveViewState(currentSessionId.value)
    currentSessionId.value = sid
    runtimes[sid].messages = []
    await loadMessages(sid)
    runtimes[sid].initialized = true
    _thinkingContentEl = null
    hasFeedback.value = false
    await nextTick()
    scrollToBottom()
  } catch {
    ElMessage.warning('新建对话失败，请重试')
  }
}

// ==================== 发送消息 ====================
async function sendMessage(text: string, attachmentPayloads: AttachmentPayload[] = []) {
  if (!text.trim() && !attachmentPayloads.length) return

  if (!currentSessionId.value) {
    await handleNewChat()
    if (!currentSessionId.value) return
    await new Promise(r => setTimeout(r, 150))
  }

  const sid = currentSessionId.value
  const rt = ensureRuntime(sid)
  if (rt.generating) {
    ElMessage.warning('当前对话正在生成中')
    return
  }

  const userAttachments = attachmentPayloads.map((p) => ({
    id: p.id || `att_${Date.now()}_${Math.random().toString(16).slice(2, 6)}`,
    kind: p.kind,
    name: p.name,
    mime: p.mime,
    size: p.size,
    previewUrl: p.kind === 'image' ? p.data_url : undefined,
  }))

  const userMsg: UIMessage = {
    role: 'user',
    content: text,
    attachments: userAttachments,
    created_at: Date.now() / 1000,
  }
  rt.messages.push(userMsg)
  await nextTick()
  scrollToBottom()

  const assistantMsg = reactive<UIMessage>({
    role: 'assistant',
    content: '',
    reasoning: '',
    steps: [],
    showThinking: true,
    isStreaming: true,
  })
  rt.messages.push(assistantMsg)
  // 新消息会生成新的思考区 DOM，重置缓存的滚动目标
  _thinkingContentEl = null

  if (DEBUG_STREAM) console.debug('[Vue] sendMessage start streaming:', text.substring(0, 50))

  const controller = streamChat(
    sid,
    text,
    (content) => {
      if (!isActiveCallback(sid, controller)) return
      // 最终回答开始时自动收起思考过程
      if (!assistantMsg.content && content) {
        assistantMsg.showThinking = false
      }
      assistantMsg.content += content
      breakReasoningStep(assistantMsg)
      scheduleRender(assistantMsg)
      scheduleStreamScroll(sid)
    },
    (reasoning) => {
      if (!isActiveCallback(sid, controller)) return
      assistantMsg.reasoning = (assistantMsg.reasoning || '') + reasoning
      appendReasoningStep(assistantMsg, reasoning)
      // 步骤文本清洗走节流渲染（各 step.clean 在 syncDerived 内更新）
      scheduleRender(assistantMsg)
      scheduleStreamScroll(sid)
    },
    (type: string, result: string, query: string) => {
      if (!isActiveCallback(sid, controller)) return
      appendTaskStep(assistantMsg, type, result, query)
      if (DEBUG_STREAM) console.debug(`[Vue] onTask type="${type}" result="${result.substring(0, 40)}"`)
    },
    () => {
      if (!isActiveCallback(sid, controller)) return
      assistantMsg.isStreaming = false
      // 流式结束，立即渲染最终内容
      scheduleRender(assistantMsg)
      if (DEBUG_STREAM) {
        console.debug(
          `[Vue] onDone | reasoning=${assistantMsg.reasoning?.length || 0} content=${assistantMsg.content.length} steps=${assistantMsg.steps?.length || 0}`,
        )
      }
      // showThinking 不再强制覆盖，保持自动收起的状态
      finishGenerating(sid, { success: true })
      // 生成完成时用户不在该会话 → 标记未读；正在查看则不标记
      if (sid !== currentSessionId.value) markUnread(sid)
      loadSessions()
    },
    (_error) => {
      if (!isActiveCallback(sid, controller)) return
      assistantMsg.isStreaming = false
      assistantMsg.showRegenerate = true
      assistantMsg.error = _error
      scheduleRender(assistantMsg)
      finishGenerating(sid, { error: _error })
      if (DEBUG_STREAM) console.debug('[Vue] onError:', _error)
    },
    attachmentPayloads,
    (title) => {
      // 迟到的事件或已停止/已删除的会话不处理
      if (!isActiveCallback(sid, controller)) return
      if (!title) return
      // 用户正在编辑该会话标题（侧边栏内联 / 顶部内联）时不覆盖输入
      if (editingSessionId.value === sid) return
      if (editingTitleInTop.value && currentSessionId.value === sid) return
      const target = (sessions.value || []).find(s => s.id === sid)
      if (!target) return
      // 本地更新；currentTitle 与侧边栏列表会自动重新渲染
      target.title = title
      if (DEBUG_STREAM) console.debug(`[Vue] onTitle: "${title}"`)
    },
  )

  if (!markGenerating(sid, controller, assistantMsg)) {
    controller.abort()
    rt.messages.splice(-2, 2)
    ElMessage.warning('当前对话正在生成中')
  }
}

function handleChatSend(payload: { text: string; attachments: AttachmentPayload[] }) {
  sendMessage(payload.text, payload.attachments)
}

/** 停止指定会话的生成（默认当前会话），不影响其他会话的流 */
function stopStreaming(sid = currentSessionId.value) {
  const rt = runtimes[sid]
  if (!rt?.controller) return
  const msg = rt.streamingMessage
  rt.controller.abort()
  finishGenerating(sid, { stopped: true })
  if (msg) msg.isStreaming = false
}

async function handleRegenerate(msg: UIMessage) {
  const sid = currentSessionId.value
  const rt = runtimes[sid]
  if (!rt || rt.generating) {
    ElMessage.warning('当前对话正在生成中')
    return
  }
  const idx = rt.messages.indexOf(msg)
  const userContent = idx > 0 ? rt.messages[idx - 1].content : ''

  msg.content = ''
  msg.reasoning = ''
  msg.showRegenerate = false
  msg.error = undefined
  msg.showThinking = true
  msg.isStreaming = true
  msg.steps = []
  msg._stepBreak = true

  _thinkingContentEl = null

  const controller = streamChat(
    sid,
    userContent,
    (content) => {
      if (!isActiveCallback(sid, controller)) return
      // 最终回答开始时自动收起思考过程
      if (!msg.content && content) {
        msg.showThinking = false
      }
      msg.content += content
      breakReasoningStep(msg)
      scheduleRender(msg)
      scheduleStreamScroll(sid)
    },
    (reasoning) => {
      if (!isActiveCallback(sid, controller)) return
      msg.reasoning = (msg.reasoning || '') + reasoning
      appendReasoningStep(msg, reasoning)
      scheduleRender(msg)
      scheduleStreamScroll(sid)
    },
    (type: string, result: string, query: string) => {
      if (!isActiveCallback(sid, controller)) return
      appendTaskStep(msg, type, result, query)
      if (DEBUG_STREAM) console.debug(`[Vue] onTask(regenerate) type="${type}"`)
    },
    () => {
      if (!isActiveCallback(sid, controller)) return
      msg.isStreaming = false
      // 流式结束，立即渲染最终内容
      scheduleRender(msg)
      if (DEBUG_STREAM) {
        console.debug(
          `[Vue] onDone(regenerate) | reasoning=${msg.reasoning?.length || 0} content=${msg.content.length} steps=${msg.steps?.length || 0}`,
        )
      }
      // showThinking 不再强制覆盖，保持自动收起的状态
      finishGenerating(sid, { success: true })
      // 生成完成时用户不在该会话 → 标记未读；正在查看则不标记
      if (sid !== currentSessionId.value) markUnread(sid)
      loadSessions()
    },
    (_error) => {
      if (!isActiveCallback(sid, controller)) return
      msg.isStreaming = false
      msg.showRegenerate = true
      msg.error = _error
      scheduleRender(msg)
      finishGenerating(sid, { error: _error })
      if (DEBUG_STREAM) console.debug('[Vue] onError(regenerate):', _error)
    },
  )

  if (!markGenerating(sid, controller, msg)) {
    controller.abort()
    ElMessage.warning('当前对话正在生成中')
  }
}

// ==================== 删除对话 ====================
async function handleDeleteSession(s: Session) {
  try {
    await ElMessageBox.confirm(
      '确定要删除该对话吗？删除后不可恢复。',
      '删除对话',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'btn-delete-confirm',
        type: 'warning',
      },
    )
    // 先中断该会话的流并清理运行时，避免迟到的回调写回已删除会话
    disposeRuntime(s.id)
    await apiDeleteSession(s.id)

    const isCurrent = s.id === currentSessionId.value
    await loadSessions()

    if (isCurrent) {
      currentSessionId.value = ''
      const slist = sessions.value || []
      if (slist.length > 0) {
        await handleSelectSession(slist[0].id)
      } else {
        await handleNewChat()
      }
    }

    ElMessage.success('对话已删除')
  } catch {
    // 取消操作
  }
}

// ==================== 编辑对话名称 ====================
function startEditSession(s: Session, event: Event) {
  event.stopPropagation()
  editingSessionId.value = s.id
  editingTitle.value = s.title || ''
  nextTick(() => {
    const input = document.getElementById(`edit-input-${s.id}`) as HTMLInputElement
    if (input) input.focus()
  })
}

async function commitEditSession(sid: string) {
  const title = editingTitle.value.trim()
  if (title) {
    await apiUpdateSessionTitle(sid, title)
  }
  editingSessionId.value = ''
  editingTitle.value = ''
  await loadSessions()
}

function cancelEdit() {
  editingSessionId.value = ''
  editingTitle.value = ''
}

function startEditTitleInTop() {
  editingTitleInTop.value = true
  titleInputValue.value = currentTitle.value
  nextTick(() => {
    const input = document.getElementById('chat-title-input') as HTMLInputElement
    if (input) { input.focus(); input.select() }
  })
}

async function commitEditTitle() {
  const newTitle = titleInputValue.value.trim()
  if (newTitle && newTitle !== currentTitle.value) {
    await apiUpdateSessionTitle(currentSessionId.value, newTitle)
  }
  editingTitleInTop.value = false
  await loadSessions()
}

function cancelEditTitle() {
  editingTitleInTop.value = false
}

// ==================== 不满意反馈 ====================
async function handleFeedback() {
  if (!currentSessionId.value || hasFeedback.value) return
  try {
    await submitFeedback(currentSessionId.value)
    hasFeedback.value = true
    ElMessage.warning('当前问答已反馈管理员，请勿重复点击～')
  } catch (err: any) {
    if (err?.status === 409) {
      hasFeedback.value = true
      ElMessage.warning('当前问答已反馈管理员，请勿重复点击～')
    }
  }
}

// ==================== 图片预览 ====================
function openImagePreview(src: string) {
  previewImage.value = src
}

async function previewAttachment(msg: UIMessage, att: ChatAttachment & { previewUrl?: string }) {
  if (!msg.id) return
  try {
    const blob = await getAttachmentContent(msg.id, att.id)
    const url = URL.createObjectURL(blob)
    if (att.kind === 'pdf') {
      window.open(url, '_blank', 'noopener')
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
      return
    }
    if (previewBlobUrl) URL.revokeObjectURL(previewBlobUrl)
    previewBlobUrl = url
    previewImage.value = previewBlobUrl
  } catch (err) {
    ElMessage.warning(err instanceof Error ? err.message : '附件预览失败')
  }
}

function closeImagePreview() {
  if (previewBlobUrl) {
    URL.revokeObjectURL(previewBlobUrl)
    previewBlobUrl = null
  }
  previewImage.value = null
}

function handlePreviewKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    closeImagePreview()
  }
}

function handleMessageContentClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.tagName === 'IMG') {
    const src = (target as HTMLImageElement).src
    if (src) openImagePreview(src)
  }
}

// ==================== 退出登录 ====================
async function handleLogout() {
  try {
    await ElMessageBox.confirm(
      '确定要退出登录吗？',
      '退出登录',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    logout()
  } catch {
    // 取消
  }
}

// ==================== 滚动处理 ====================
async function scrollToBottom() {
  await nextTick()
  if (messageArea.value) {
    messageArea.value.scrollTop = messageArea.value.scrollHeight
  }
}

/**
 * 流式期间的高频滚动节流。
 *
 * 原先每个 token 都会执行一次「读 scrollHeight + 写 scrollTop」，属于强制同步布局
 * （layout thrashing），并且每次都 querySelectorAll 遍历 DOM 找 .thinking-steps，
 * 开销随会话长度（消息数、图片数）增长——这是「聊得越久越卡」的主因。
 * 现在统一收敛为每帧最多一次，并缓存思考区元素，避免重复查询。
 */
let _streamScrollScheduled = false
let _thinkingContentEl: HTMLElement | null = null

function scheduleStreamScroll(sid = currentSessionId.value) {
  // 后台会话产生的 token 不得滚动当前视图
  if (sid !== currentSessionId.value) return
  if (_streamScrollScheduled) return
  _streamScrollScheduled = true
  requestAnimationFrame(() => {
    _streamScrollScheduled = false

    // 1) 消息区跟随底部
    if (userAtBottom.value && messageArea.value) {
      messageArea.value.scrollTop = messageArea.value.scrollHeight
    }

    // 2) 思考过程内容区跟随底部（缓存元素；消息重建后自动重新查询）
    if (!_thinkingContentEl || !_thinkingContentEl.isConnected) {
      const list = messageArea.value?.querySelectorAll('.thinking-steps')
      _thinkingContentEl = list && list.length > 0 ? (list[list.length - 1] as HTMLElement) : null
    }
    if (_thinkingContentEl) {
      _thinkingContentEl.scrollTop = _thinkingContentEl.scrollHeight
    }
  })
}

function handleMessageScroll() {
  if (!messageArea.value) return
  const el = messageArea.value
  userAtBottom.value = el.scrollTop + el.clientHeight >= el.scrollHeight - 50

  // 向上滚动加载更多
  if (el.scrollTop < 50 && hasMoreMessages.value && !loadingMessages.value) {
    loadMoreMessages()
  }
}

function handleSidebarScroll() {
  if (!sidebarList.value) return
  const el = sidebarList.value
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 20) {
    loadMoreSessions()
  }
}

watch(
  () => currentMessages.value.length,
  () => {
    if (userAtBottom.value) {
      scrollToBottom()
    }
  },
)

// 图片预览打开时自动聚焦遮罩以支持 ESC 关闭
watch(previewImage, (val) => {
  if (val) {
    nextTick(() => {
      const overlay = document.querySelector('.image-preview-overlay') as HTMLElement
      overlay?.focus()
    })
  }
})

async function loadMoreMessages() {
  if (loadingMessages.value || !hasMoreMessages.value) return
  const firstMsg = currentMessages.value[0]
  if (!firstMsg?.id) return

  loadingMessages.value = true
  const oldHeight = messageArea.value?.scrollHeight || 0

  try {
    const res = await getSessionMessages(currentSessionId.value, 50, firstMsg.id)
    const visible = res.messages.filter(isVisibleMessage)
    const olderMsgs: UIMessage[] = visible.map(m => ({
      id: m.id,
      role: m.role as 'user' | 'assistant',
      content: m.content,
      attachments: m.attachments || [],
      reasoning: m.reasoning_content || '',
      steps: buildHistorySteps(m),
      showThinking: !!(m.reasoning_content || m.steps?.length || m.tasks?.length),
      isStreaming: false,
      created_at: m.created_at,
    }))

    if (currentRuntime.value) {
      currentRuntime.value.messages = [...olderMsgs, ...currentRuntime.value.messages]
    }
    hasMoreMessages.value = res.has_more

    await nextTick()
    if (messageArea.value) {
      const newHeight = messageArea.value.scrollHeight
      messageArea.value.scrollTop = newHeight - oldHeight
    }
  } catch {
    // handled
  }
  loadingMessages.value = false
}

// ==================== 初始化 ====================
onMounted(async () => {
  await loadSessions()
  const list = sessions.value || []
  if (list.length === 0) {
    await handleNewChat()
  } else {
    currentSessionId.value = list[0].id
    await loadMessages(list[0].id)
    runtimes[list[0].id].initialized = true
    await loadFeedbackStatus(list[0].id)
    await nextTick()
    scrollToBottom()
  }
})

onBeforeUnmount(() => {
  disposeAllRuntimes()
  document.removeEventListener('mousemove', onResizerMouseMove)
  document.removeEventListener('mouseup', onResizerMouseUp)
})
</script>

<template>
  <div class="app-layout">
    <!-- ==================== 侧边栏 ==================== -->
    <aside class="sidebar" :style="{ width: sidebarWidth + 'px' }">
      <div class="sidebar-resizer" :class="{ active: isDragging }" @mousedown="onResizerMouseDown"></div>

      <!-- 新对话按钮 -->
      <div class="sidebar-new-chat">
        <button class="btn-new-chat" @click="handleNewChat">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3v10M3 8h10"/>
          </svg>
          新建对话
        </button>
      </div>

      <!-- 搜索框 -->
      <div class="sidebar-search">
        <div class="search-wrapper">
          <svg class="search-icon" viewBox="0 0 15 15" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="6.5" cy="6.5" r="5"/><path d="M10.5 10.5L14 14"/>
          </svg>
          <input
            type="text"
            class="search-input"
            placeholder="按名称搜索..."
            v-model="searchKeyword"
          />
        </div>
      </div>

      <!-- 对话列表 -->
      <div class="sidebar-list" ref="sidebarList" @scroll="handleSidebarScroll">
        <div
          v-for="s in filteredSessions"
          :key="s.id"
          class="chat-item"
          :class="{ active: s.id === currentSessionId, unread: runtimes[s.id]?.unread }"
          @click="handleSelectSession(s.id)"
        >
          <div class="chat-item-icon">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
              <rect x="1" y="1.5" width="12" height="9" rx="1.5"/><path d="M4 6.5h6M4 9h4"/>
            </svg>
          </div>

          <!-- 编辑模式 -->
          <div v-if="editingSessionId === s.id" class="chat-item-edit-row" @click.stop>
            <input
              :id="`edit-input-${s.id}`"
              v-model="editingTitle"
              class="chat-item-edit-input"
              @keydown.enter="commitEditSession(s.id)"
              @keydown.escape="cancelEdit()"
              @blur="commitEditSession(s.id)"
            />
          </div>

          <!-- 正常模式 -->
          <div v-else class="chat-item-info">
            <div class="chat-item-title">
              <span class="chat-item-title-text">{{ s.title || '新对话' }}</span>
              <span
                v-if="isSessionGenerating(s.id)"
                class="gen-badge"
                title="该对话正在生成中"
                aria-label="该对话正在生成中"
              ><i class="gen-badge__dot"></i>正在生成</span>
              <span v-else-if="runtimes[s.id]?.error" class="gen-badge gen-badge--error">生成失败</span>
              <span
                v-else-if="runtimes[s.id]?.unread"
                class="unread-dot"
                title="有新回复"
                aria-label="有新回复未读"
              ></span>
            </div>
            <div v-if="s.last_message" class="chat-item-preview">{{ truncatePreview(s.last_message) }}</div>
          </div>

          <!-- 操作按钮（hover 显示） -->
          <div v-if="editingSessionId !== s.id" class="chat-item-actions">
            <button class="chat-item-action-btn edit" title="编辑名称" @click.stop="startEditSession(s, $event)">
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M10 2l2 2-8 8H2v-2l8-8z"/>
              </svg>
            </button>
            <button
              class="chat-item-action-btn delete"
              title="删除对话"
              @click.stop="handleDeleteSession(s)"
            >
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M2 4h10M5 4V3a1 1 0 011-1h2a1 1 0 011 1v1M11 4v7a1 1 0 01-1 1H4a1 1 0 01-1-1V4"/>
              </svg>
            </button>
          </div>
        </div>
        <div v-if="loadingMore" class="sidebar-loading">加载中...</div>
      </div>
    </aside>

    <!-- ==================== 主区域 ==================== -->
    <div class="main-area">
      <!-- 顶部栏 -->
      <header class="top-bar">
        <div class="chat-title-area">
          <span
            v-if="!editingTitleInTop"
            class="chat-title-text"
            @click="startEditTitleInTop"
          >{{ currentTitle }}</span>
          <input
            v-else
            id="chat-title-input"
            class="chat-title-input"
            v-model="titleInputValue"
            @keydown.enter="commitEditTitle"
            @keydown.escape="cancelEditTitle"
            @blur="commitEditTitle"
          />
          <span
            v-if="isCurrentStreaming"
            class="gen-badge gen-badge--title"
            title="该对话正在生成中"
            aria-label="该对话正在生成中"
          ><i class="gen-badge__dot"></i>正在生成</span>
          <button
            class="btn-feedback-top"
            :class="{ active: hasFeedback }"
            @click="handleFeedback"
            title="不满意本次问答"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M2.5 2.5h11v8H7l-3.5 3v-3H2.5z"/>
              <path d="M5.5 6h5M5.5 8.5h3"/>
              <circle cx="12.5" cy="3.5" r="2.5" fill="#FAAD14" stroke="none"/>
              <path d="M12.5 2.5v1.2M12.5 4.3v.2" stroke="#fff" stroke-width="1.2"/>
            </svg>
            {{ hasFeedback ? '已反馈' : '不满意本次问答' }}
          </button>
        </div>

        <div class="user-info">
          <span class="user-name">{{ currentUser?.realname || currentUser?.username || '' }}</span>
          <div class="user-avatar">{{ ((currentUser?.realname || currentUser?.username || '?')[0] || '?').toUpperCase() }}</div>
          <button class="btn-logout" @click="handleLogout">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M5 2H3a1 1 0 00-1 1v8a1 1 0 001 1h2M10 10l3-3-3-3M13 7H5"/>
            </svg>
            退出
          </button>
        </div>
      </header>

      <!-- 消息区域 -->
      <div class="message-area" ref="messageArea" @scroll="handleMessageScroll">
        <div v-if="loadingMessages" class="loading-hint">加载中...</div>

        <template v-for="(msg, i) in currentMessages" :key="msg.id || i">
          <!-- 时间分隔线 -->
          <div v-if="showTimeDivider(msg, i)" class="msg-time-divider">
            {{ msg.created_at ? formatTime(msg.created_at) : '' }}
          </div>

          <!-- 消息组 -->
          <div class="msg-group" :class="msg.role">
            <!-- 头像 -->
            <div class="msg-avatar">
              <img
                v-if="msg.role === 'assistant'"
                src="/origin.png"
                alt="assistant"
                class="avatar-img"
              />
              <span v-else>{{ ((currentUser?.realname || currentUser?.username || '?')[0] || '?').toUpperCase() }}</span>
            </div>

            <!-- 消息主体 -->
            <div class="msg-body">
              <!-- 元信息 -->
              <div class="msg-meta">
                <span class="msg-sender">{{ msg.role === 'assistant' ? '智能客服助手' : '我' }}</span>
                <span class="msg-time" v-if="msg.created_at">{{ formatMessageTime(msg.created_at) }}</span>
              </div>

              <!-- 气泡 -->
              <div class="msg-bubble">
                <!-- 用户附件卡片（只读） -->
                <div
                  v-if="msg.role === 'user' && msg.attachments && msg.attachments.length"
                  class="msg-attachments"
                >
                  <div
                    v-for="att in msg.attachments"
                    :key="att.id"
                    class="msg-attachment-wrapper"
                    @click="previewAttachment(msg, att)"
                  >
                    <AttachmentCard :attachment="att" clickable />
                  </div>
                </div>

                <!-- 思考过程 -->
                <div
                  v-if="msg.role === 'assistant' && (msg.reasoning || msg.isStreaming || (msg.steps && msg.steps.length > 0))"
                  class="thinking-block"
                  :class="{ collapsed: !msg.showThinking }"
                >
                  <div class="thinking-header" @click="msg.showThinking = !msg.showThinking">
                    <svg class="thinking-clock-icon" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                      <circle cx="7" cy="7" r="5.5"/><path d="M7 4v3.5L9 9"/>
                    </svg>
                    <!-- 动态标题：思考中（带动画点）/ 思考过程 -->
                    <span v-if="msg.isStreaming && !msg.content" class="thinking-label thinking-active">
                      思考中
                      <span class="thinking-dots">
                        <span class="thinking-dot"></span>
                        <span class="thinking-dot"></span>
                        <span class="thinking-dot"></span>
                      </span>
                    </span>
                    <span v-else class="thinking-label">思考过程</span>
                    <span class="thinking-toggle">
                      <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M3 5l3 3 3-3"/>
                      </svg>
                    </span>
                  </div>
                  <!-- 时间线：reasoning 片段与 Skill 结果按到达顺序交错，刷新后由落库 steps 原样回放 -->
                  <div class="thinking-steps">
                    <template v-for="(s, si) in msg.steps || []" :key="si">
                      <div v-if="s.kind === 'reasoning'" class="reasoning-text">{{ s.clean ?? cleanReasoning(s.text || '') }}</div>
                      <div v-else-if="s.task?.type === 'knowledge_retrieval'" class="retrieval-card">
                        <div class="retrieval-header">
                          <svg class="retrieval-icon" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                            <circle cx="6" cy="6" r="4"/><path d="M9 9l3.5 3.5"/>
                          </svg>
                          <span class="retrieval-title">知识库检索结果</span>
                          <span v-if="s.task?.query" class="retrieval-query" :title="s.task?.query">{{ s.task?.query }}</span>
                        </div>
                        <div class="retrieval-text">{{ s.task?.hitText || s.task?.result }}</div>
                        <div v-if="s.task?.images && s.task.images.length > 0" class="retrieval-images">
                          <div
                            v-for="(img, ii) in s.task?.images || []"
                            :key="ii"
                            class="retrieval-image"
                            :title="img.source || img.alt"
                            @click="openImagePreview(img.path)"
                          >
                            <img :src="img.path" :alt="img.alt" />
                            <span class="retrieval-image-alt">{{ img.alt }}</span>
                          </div>
                        </div>
                      </div>
                      <div v-else-if="s.task" class="task-item">
                        <span class="task-badge">{{ s.task?.type }}</span>
                        <span class="task-result">{{ s.task?.result }}</span>
                      </div>
                    </template>
                    <!-- 占位：等待思考内容 -->
                    <div v-if="msg.isStreaming && (!msg.steps || msg.steps.length === 0)" class="thinking-placeholder">
                      正在分析...
                    </div>
                  </div>
                </div>

                <!-- 分隔线 -->
                <div
                  v-if="msg.role === 'assistant' && (msg.reasoning || (msg.steps && msg.steps.length > 0)) && msg.content"
                  class="thinking-divider"
                ></div>

                <!-- 内容（实时 markdown 渲染，流式期间节流防闪动） -->
                <div
                  v-if="msg.content"
                  class="msg-content"
                  v-html="msg._renderedHtml ?? renderMarkdown(msg.content)"
                  @click="handleMessageContentClick"
                ></div>

                <!-- 流式光标 -->
                <span v-if="msg.isStreaming" class="streaming-cursor">▊</span>

                <!-- 错误提示 -->
                <div
                  v-if="msg.error"
                  class="msg-error"
                >{{ msg.error }}</div>

                <!-- 重新生成按钮 -->
                <button
                  v-if="msg.showRegenerate"
                  class="regenerate-btn"
                  @click="handleRegenerate(msg)"
                >
                  <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M1 7a6 6 0 0111.5-2.5M13 7a6 6 0 01-11.5 2.5"/><path d="M10 1.5l.5 3-3-.5M4 12.5l-.5-3 3 .5"/>
                  </svg>
                  重新生成
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- 底部区域 -->
      <div class="bottom-area">
        <ChatInput
          :key="currentSessionId"
          :streaming="isCurrentStreaming"
          v-model="currentDraft"
          @send="handleChatSend"
          @stop="stopStreaming"
        />
      </div>
    </div>

    <!-- ==================== 图片预览遮罩 ==================== -->
    <Teleport to="body">
      <div
        v-if="previewImage"
        class="image-preview-overlay"
        @click="closeImagePreview"
        @keydown="handlePreviewKeydown"
        tabindex="0"
      >
        <button class="image-preview-close" @click.stop="closeImagePreview" title="关闭预览">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 3l10 10M13 3L3 13"/>
          </svg>
        </button>
        <img
          :src="previewImage"
          class="image-preview-img"
          @click.stop
          alt="预览图片"
        />
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  font-family: var(--font-family);
  background: var(--color-bg-page);
  -webkit-font-smoothing: antialiased;
}

/* ==================== 侧边栏 ==================== */
.sidebar {
  height: 100vh;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border-light);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
}

.sidebar-resizer {
  position: absolute;
  right: -2px;
  top: 0;
  bottom: 0;
  width: 4px;
  cursor: col-resize;
  z-index: 20;
  transition: background 0.2s ease;
}
.sidebar-resizer:hover,
.sidebar-resizer.active {
  background: var(--color-primary);
}

.sidebar-new-chat {
  padding: 16px;
  border-bottom: 1px solid var(--color-border-light);
}

.btn-new-chat {
  width: 100%;
  height: 36px;
  background: var(--color-primary);
  border: none;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s ease;
  font-family: inherit;
}
.btn-new-chat:hover { background: var(--color-primary-hover); }
.btn-new-chat:active { background: var(--color-primary-active); transform: scale(0.98); }
.btn-new-chat svg { width: 16px; height: 16px; }

.sidebar-search {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-light);
}

.search-wrapper { position: relative; }

.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 15px;
  height: 15px;
  color: var(--color-text-tertiary);
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: 32px;
  padding: 0 12px 0 32px;
  font-size: 13px;
  color: var(--color-text-primary);
  background: var(--color-bg-page);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  outline: none;
  transition: border-color 0.2s ease;
  font-family: inherit;
}
.search-input::placeholder { color: var(--color-text-disabled); }
.search-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(43,103,255,0.1);
}

/* 对话列表 */
.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px;
}
.sidebar-list::-webkit-scrollbar { width: 4px; }
.sidebar-list::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 2px;
}

.chat-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.15s ease;
  gap: 10px;
  position: relative;
  margin-bottom: 2px;
}
.chat-item:hover { background: var(--color-bg-hover); }
.chat-item.active { background: var(--color-primary-light); }
.chat-item.active .chat-item-title { color: var(--color-primary); }

.chat-item-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, #2B67FF, #3D82F2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.chat-item-icon svg { width: 14px; height: 14px; color: #fff; }

.chat-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-item-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  min-width: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
}
.chat-item-title-text {
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ==================== 会话生成状态徽标 ==================== */
.gen-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  flex-shrink: 0;
  padding: 2px var(--spacing-sm);
  font-size: 11px;
  font-weight: 400;
  line-height: 1.4;
  color: var(--color-primary);
  background: var(--color-primary-light);
  border-radius: var(--radius-round);
}
.gen-badge--title {
  font-size: 12px;
  margin-left: var(--spacing-sm);
  vertical-align: middle;
}
.gen-badge--error {
  color: var(--color-danger);
  background: transparent;
}
.gen-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-round);
  background: currentColor;
  animation: gen-pulse 1.2s ease-in-out infinite;
}
@keyframes gen-pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: .35; }
}

/* ==================== 未读状态 ==================== */
.chat-item.unread .chat-item-title {
  font-weight: 600;
  color: var(--color-text-primary);
}
.unread-dot {
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  border-radius: var(--radius-round);
  background: var(--color-primary);
}

.chat-item-preview {
  font-size: 12px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-item-actions {
  display: none;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.chat-item:hover .chat-item-actions { display: flex; }

.chat-item-action-btn {
  width: 26px;
  height: 26px;
  border: none;
  background: none;
  cursor: pointer;
  color: var(--color-text-tertiary);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.chat-item-action-btn:hover { background: var(--color-bg-hover); color: var(--color-text-secondary); }
.chat-item-action-btn.edit:hover { background: var(--color-primary-light); color: var(--color-primary); }
.chat-item-action-btn.delete:hover { background: #FFF0F0; color: var(--color-danger); }
.chat-item-action-btn svg { width: 14px; height: 14px; }

.chat-item-edit-row {
  flex: 1;
  min-width: 0;
}

.chat-item-edit-input {
  width: 100%;
  height: 28px;
  padding: 0 8px;
  font-size: 13px;
  color: var(--color-text-primary);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  outline: none;
  font-family: inherit;
  background: var(--color-bg-card);
  box-shadow: 0 0 0 2px rgba(43,103,255,0.15);
}

.sidebar-loading {
  text-align: center;
  padding: 12px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

/* ==================== 主区域 ==================== */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 400px;
  height: 100vh;
  background: var(--color-bg-page);
}

/* 顶部栏 */
.top-bar {
  height: 56px;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}

.chat-title-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-title-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 24px;
  cursor: text;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  transition: all 0.2s ease;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chat-title-text:hover {
  border-color: var(--color-border);
  background: var(--color-bg-hover);
}

.chat-title-input {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  padding: 2px 6px;
  outline: none;
  font-family: inherit;
  background: var(--color-bg-card);
  width: 260px;
  line-height: 24px;
  box-shadow: 0 0 0 2px rgba(43,103,255,0.15);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-name {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  background: linear-gradient(135deg, #a8c0ff, #3f2b96);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
}

.btn-logout {
  height: 32px;
  padding: 0 14px;
  font-size: 13px;
  color: var(--color-text-secondary);
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  display: flex;
  align-items: center;
  gap: 4px;
}
.btn-logout:hover {
  color: var(--color-danger);
  border-color: var(--color-danger);
  background: #FFF5F5;
}
.btn-logout svg { width: 14px; height: 14px; }

/* ==================== 消息区域 ==================== */
.message-area {
  position: relative;
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.message-area::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: url('/origin.png') center/contain no-repeat;
  opacity: 0.06;
  z-index: 0;
  pointer-events: none;
}
.message-area::-webkit-scrollbar { width: 5px; }
.message-area::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 3px;
}

.loading-hint {
  text-align: center;
  padding: 12px;
  font-size: 13px;
  color: var(--color-text-tertiary);
}

/* 时间分隔线 */
.msg-time-divider {
  text-align: center;
  font-size: 12px;
  color: var(--color-text-tertiary);
  padding: 16px 0 12px;
}

/* 消息组 */
.msg-group {
  display: flex;
  gap: 10px;
  margin-bottom: 4px;
}
.msg-group.assistant {
  flex-direction: row;
  align-items: flex-start;
}
.msg-group.user {
  flex-direction: row-reverse;
  align-items: flex-start;
}

.msg-body {
  display: flex;
  flex-direction: column;
  max-width: 70%;
}
.msg-group.user .msg-body {
  align-items: flex-end;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  padding: 0 4px;
}
.msg-sender {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
}
.msg-time {
  font-size: 11px;
  color: var(--color-text-tertiary);
}
.msg-group.user .msg-meta {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 500;
  margin-top: 18px;
}
.msg-group.assistant .msg-avatar {
  color: #fff;
}
.msg-group.user .msg-avatar {
  background: linear-gradient(135deg, #a8c0ff, #3f2b96);
  color: #fff;
}
.avatar-img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}

/* 消息气泡 */
.msg-bubble {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 14px;
  line-height: 22px;
  word-break: break-word;
  position: relative;
  box-shadow: var(--shadow-sm);
  max-width: 100%;
}
.msg-group.assistant .msg-bubble {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  border-top-left-radius: 4px;
  border: 1px solid var(--color-border-light);
}
.msg-group.user .msg-bubble {
  background: var(--color-primary);
  color: #FFFFFF;
  border-top-right-radius: 4px;
  box-shadow: 0 2px 8px rgba(43,103,255,0.25);
}

/* 思考过程 */
.thinking-block {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  margin-bottom: 12px;
  overflow: hidden;
  background: #FAFBFC;
}
.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  cursor: pointer;
  user-select: none;
  transition: background 0.15s ease;
}
.thinking-header:hover { background: var(--color-bg-hover); }
.thinking-header svg { width: 14px; height: 14px; }
.thinking-toggle {
  margin-left: auto;
  transition: transform 0.2s ease;
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}
.thinking-toggle svg { width: 12px; height: 12px; }
.thinking-block.collapsed .thinking-toggle {
  transform: rotate(-90deg);
}
.thinking-clock-icon {
  flex-shrink: 0;
}
.thinking-label {
  font-size: 12px;
}
.thinking-label.thinking-active {
  color: var(--color-primary);
  font-weight: 500;
}
.thinking-dots {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-left: 4px;
  vertical-align: middle;
}
.thinking-dot {
  display: inline-block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: thinkingPulse 1.2s ease-in-out infinite;
}
.thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes thinkingPulse {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}
/* 思考过程时间线：reasoning 片段与任务卡片按序排列，统一滚动 */
.thinking-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  line-height: 20px;
  max-height: 300px;
  overflow-y: auto;
  border-top: 1px solid var(--color-border-light);
}
.thinking-block.collapsed .thinking-steps {
  display: none;
}
.thinking-steps::-webkit-scrollbar { width: 3px; }
.thinking-steps::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 2px;
}

/* 任务执行项 */
.task-item {
  padding: 6px 8px;
  background: #F0F4FF;
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--color-primary);
}
.task-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-primary);
  background: #E0E8FF;
  padding: 1px 6px;
  border-radius: 3px;
  margin-right: 6px;
}
.task-result {
  display: block;
  margin-top: 4px;
  max-height: 160px;
  overflow-y: auto;
  white-space: pre-wrap;
  color: var(--color-text-secondary);
  word-break: break-word;
}
.task-result::-webkit-scrollbar { width: 3px; }
.task-result::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 2px;
}

/* 思考推理文本 */
.reasoning-text {
  white-space: pre-wrap;
  word-break: break-word;
}

/* 占位提示 */
.thinking-placeholder {
  color: var(--color-text-disabled);
  font-style: italic;
}

/* knowledge_retrieval 结果卡片（时间线中的一个步骤） */
.retrieval-card {
  border: 1px solid #E0E8FF;
  border-left: 3px solid var(--color-primary);
  border-radius: var(--radius-sm);
  background: #F7F9FF;
  padding: 8px 10px;
}
.retrieval-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  min-width: 0;
}
.retrieval-icon {
  width: 13px;
  height: 13px;
  flex: none;
  color: var(--color-primary);
}
.retrieval-title {
  flex: none;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-primary);
}
.retrieval-query {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: var(--color-text-tertiary);
  background: #E0E8FF;
  border-radius: 3px;
  padding: 1px 6px;
}
.retrieval-text {
  max-height: 220px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 19px;
  color: var(--color-text-secondary);
}
.retrieval-text::-webkit-scrollbar { width: 3px; }
.retrieval-text::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 2px;
}
.retrieval-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.retrieval-image {
  width: 96px;
  cursor: zoom-in;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.retrieval-image img {
  width: 96px;
  height: 72px;
  object-fit: cover;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  background: #fff;
}
.retrieval-image-alt {
  font-size: 11px;
  color: var(--color-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thinking-divider {
  height: 1px;
  background: var(--color-border-light);
  margin: 12px 0;
}

/* 消息内容 */
.msg-content :deep(p) { margin-bottom: 6px; }
.msg-content :deep(p:last-child) { margin-bottom: 0; }
.msg-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: opacity 0.15s ease;
}
.msg-content :deep(img:hover) {
  opacity: 0.85;
}
.msg-content :deep(strong) { font-weight: 600; }
.msg-content :deep(code) {
  background: rgba(0,0,0,0.06);
  padding: 2px 5px;
  border-radius: 3px;
  font-size: 13px;
}
.msg-content :deep(pre) {
  background: #f5f6fa;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  margin: 8px 0;
}
.msg-content :deep(pre code) {
  background: transparent;
  padding: 0;
}
.msg-content :deep(ul), .msg-content :deep(ol) {
  padding-left: 20px;
  margin: 4px 0;
}
.msg-content :deep(blockquote) {
  border-left: 3px solid var(--color-primary);
  padding-left: 10px;
  color: var(--color-text-secondary);
  margin: 6px 0;
}

.streaming-cursor {
  display: inline;
  animation: blink 1s step-end infinite;
  color: var(--color-primary);
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 重新生成按钮 */
.regenerate-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-primary);
  background: var(--color-primary-light);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
}
.regenerate-btn:hover {
  background: var(--color-primary);
  color: #fff;
}
.regenerate-btn svg { width: 13px; height: 13px; }

/* 错误信息 */
.msg-error {
  margin-top: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: #ef4444;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius-sm);
  line-height: 1.5;
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
}

/* ==================== 底部区域 ==================== */
.bottom-area {
  background: var(--color-bg-card);
  border-top: 1px solid var(--color-border-light);
  padding: 16px 24px;
  flex-shrink: 0;
}

.msg-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.msg-attachment-wrapper {
  display: inline-flex;
}

/* 顶部反馈按钮 */
.btn-feedback-top {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 14px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  white-space: nowrap;
  flex-shrink: 0;
}
.btn-feedback-top:hover {
  color: var(--color-warning);
  border-color: var(--color-warning);
  background: #FFF8EC;
}
.btn-feedback-top.active {
  color: var(--color-text-disabled);
  border-color: var(--color-border-light);
  cursor: default;
  background: var(--color-bg-hover);
}
.btn-feedback-top svg { width: 16px; height: 16px; flex-shrink: 0; }

.input-row { position: relative; }
.input-wrapper-bottom { position: relative; }

.msg-input {
  width: 100%;
  min-height: 128px;
  max-height: 250px;
  padding: 14px 48px 14px 16px;
  font-size: 14px;
  color: var(--color-text-primary);
  background: var(--color-bg-page);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  outline: none;
  resize: none;
  font-family: inherit;
  line-height: 22px;
  transition: border-color 0.2s ease;
}
.msg-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(43,103,255,0.1);
}
.msg-input:disabled {
  background: var(--color-bg-hover);
  color: var(--color-text-disabled);
  cursor: not-allowed;
}
.msg-input::placeholder { color: var(--color-text-disabled); }

.btn-send {
  position: absolute;
  right: 10px;
  bottom: 10px;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}
.btn-send:hover { background: var(--color-primary-hover); }
.btn-send:active { background: var(--color-primary-active); transform: scale(0.95); }
.btn-send:disabled {
  background: var(--color-text-disabled);
  cursor: not-allowed;
}
.btn-send svg { width: 14px; height: 14px; color: #fff; }
.btn-send.stop { background: var(--color-danger); }
.btn-send.stop:hover { background: #E03636; }

/* ==================== 图片预览遮罩 ==================== */
.image-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: previewFadeIn 0.2s ease;
  outline: none;
}

@keyframes previewFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.image-preview-close {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 40px;
  height: 40px;
  border: none;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 50%;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease;
  z-index: 1;
}
.image-preview-close:hover {
  background: rgba(255, 255, 255, 0.3);
}
.image-preview-close svg {
  width: 20px;
  height: 20px;
}

.image-preview-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: var(--radius-md);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
  user-select: none;
}
</style>
