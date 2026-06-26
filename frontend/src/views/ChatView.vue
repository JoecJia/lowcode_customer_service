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
import type { Session } from '../api/chat'
import { useAuth } from '../composables/useAuth'

const { currentUser, logout } = useAuth()

// ==================== DEBUG 开关 ====================
const DEBUG_STREAM = true

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
const messages = ref<UIMessage[]>([])
const loadingMessages = ref(false)
const hasMoreMessages = ref(false)

const currentTitle = computed(() => {
  const s = (sessions.value || []).find(s => s.id === currentSessionId.value)
  return s?.title || '新对话'
})

// ==================== 输入状态 ====================
const inputText = ref('')
const isStreaming = ref(false)
const isComposing = ref(false)
let abortController: AbortController | null = null

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

// ==================== 类型 ====================
interface TaskInfo {
  type: string
  result: string
}

interface UIMessage {
  id?: number
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  tasks?: TaskInfo[]
  showThinking?: boolean
  isStreaming?: boolean
  showRegenerate?: boolean
  created_at?: number
}

// ==================== 工具函数 ====================

// 自定义 marked 渲染器：将相对路径的图片 src 转为服务端绝对路径
const markedRenderer = new marked.Renderer()
const originalImageRenderer = markedRenderer.image.bind(markedRenderer)
markedRenderer.image = function (token: any): string {
  const href: string = token.href
  // ../assets/xxx → /assets/xxx  （兜底修正，防止 LLM 输出的相对路径图片显示为裂图）
  if (href.startsWith('../assets/') || href.includes('/../assets/')) {
    token.href = href.replace(/(?:\.\.\/)+assets\//g, '/assets/')
  }
  return originalImageRenderer(token)
}

marked.setOptions({ breaks: true, gfm: true, renderer: markedRenderer })

function renderMarkdown(text: string): string {
  if (!text) return ''
  return marked.parse(text) as string
}

function cleanReasoning(text: string): string {
  return text.replace(/<\/?think>/gi, '').replace(/<THINK_V2>/gi, '').trim()
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
  const prev = messages.value[i - 1]
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
  try {
    const res = await getSessionMessages(sessionId)
    const visible = res.messages.filter(isVisibleMessage)
    messages.value = visible.map((m) => ({
      id: m.id,
      role: m.role as 'user' | 'assistant',
      content: m.content,
      reasoning: m.reasoning_content || '',
      showThinking: !!(m.reasoning_content),
      isStreaming: false,
      created_at: m.created_at,
    }))
    hasMoreMessages.value = res.has_more
  } catch {
    messages.value = []
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
async function handleSelectSession(sid: string) {
  if (isStreaming.value) return
  currentSessionId.value = sid
  await loadMessages(sid)
  await loadFeedbackStatus(sid)
  await nextTick()
  scrollToBottom()
}

async function handleNewChat() {
  if (isStreaming.value) return
  const sid = await createSession()
  if (sid) {
    await loadSessions()
    currentSessionId.value = sid
    messages.value = []
    await loadMessages(sid)
    hasFeedback.value = false
    await nextTick()
    scrollToBottom()
  }
}

// ==================== 发送消息 ====================
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isStreaming.value) return

  if (!currentSessionId.value) {
    await handleNewChat()
    if (!currentSessionId.value) return
    await new Promise(r => setTimeout(r, 150))
  }

  inputText.value = ''

  const userMsg: UIMessage = {
    role: 'user',
    content: text,
    created_at: Date.now() / 1000,
  }
  messages.value.push(userMsg)
  await nextTick()
  scrollToBottom()

  const assistantMsg = reactive<UIMessage>({
    role: 'assistant',
    content: '',
    reasoning: '',
    tasks: [],
    showThinking: true,
    isStreaming: true,
  })
  messages.value.push(assistantMsg)

  isStreaming.value = true

  if (DEBUG_STREAM) console.debug('[Vue] sendMessage start streaming:', text.substring(0, 50))

  abortController = streamChat(
    currentSessionId.value,
    text,
    (content) => {
      // 最终回答开始时自动收起思考过程
      if (!assistantMsg.content && content) {
        assistantMsg.showThinking = false
      }
      assistantMsg.content += content
      if (DEBUG_STREAM) {
        const preview = content.substring(0, 40).replace(/\n/g, '\\n')
        console.debug(`[Vue] onContent +="${preview}" total=${assistantMsg.content.length}`)
      }
      if (userAtBottom.value) scrollToBottom()
    },
    (reasoning) => {
      assistantMsg.reasoning = (assistantMsg.reasoning || '') + reasoning
      if (DEBUG_STREAM) {
        const preview = reasoning.substring(0, 40).replace(/\n/g, '\\n')
        console.debug(`[Vue] onReasoning +="${preview}" total=${assistantMsg.reasoning!.length}`)
      }
      if (userAtBottom.value) scrollToBottom()
    },
    (type: string, result: string) => {
      if (!assistantMsg.tasks) assistantMsg.tasks = []
      assistantMsg.tasks.push({ type, result })
      if (DEBUG_STREAM) console.debug(`[Vue] onTask type="${type}" result="${result.substring(0, 40)}"`)
    },
    () => {
      assistantMsg.isStreaming = false
      if (DEBUG_STREAM) {
        console.debug(
          `[Vue] onDone | reasoning=${assistantMsg.reasoning?.length || 0} content=${assistantMsg.content.length} tasks=${assistantMsg.tasks?.length || 0}`,
        )
      }
      // showThinking 不再强制覆盖，保持自动收起的状态
      isStreaming.value = false
      abortController = null
      loadSessions()
    },
    (_error) => {
      assistantMsg.isStreaming = false
      assistantMsg.showRegenerate = true
      isStreaming.value = false
      abortController = null
      if (DEBUG_STREAM) console.debug('[Vue] onError:', _error)
    },
  )
}

function stopStreaming() {
  if (abortController) {
    abortController.abort()
    abortController = null
    isStreaming.value = false
    const last = messages.value[messages.value.length - 1]
    if (last && last.isStreaming) {
      last.isStreaming = false
    }
  }
}

async function handleRegenerate(msg: UIMessage) {
  msg.content = ''
  msg.reasoning = ''
  msg.showRegenerate = false
  msg.showThinking = true
  msg.isStreaming = true
  msg.tasks = []

  isStreaming.value = true

  abortController = streamChat(
    currentSessionId.value,
    messages.value[messages.value.length - 2].content,
    (content) => {
      // 最终回答开始时自动收起思考过程
      if (!msg.content && content) {
        msg.showThinking = false
      }
      msg.content += content
      if (DEBUG_STREAM) {
        const preview = content.substring(0, 40).replace(/\n/g, '\\n')
        console.debug(`[Vue] onContent(regenerate) +="${preview}" total=${msg.content.length}`)
      }
      if (userAtBottom.value) scrollToBottom()
    },
    (reasoning) => {
      msg.reasoning = (msg.reasoning || '') + reasoning
      if (DEBUG_STREAM) {
        const preview = reasoning.substring(0, 40).replace(/\n/g, '\\n')
        console.debug(`[Vue] onReasoning(regenerate) +="${preview}" total=${msg.reasoning!.length}`)
      }
      if (userAtBottom.value) scrollToBottom()
    },
    (type: string, result: string) => {
      if (!msg.tasks) msg.tasks = []
      msg.tasks.push({ type, result })
      if (DEBUG_STREAM) console.debug(`[Vue] onTask(regenerate) type="${type}"`)
    },
    () => {
      msg.isStreaming = false
      if (DEBUG_STREAM) {
        console.debug(
          `[Vue] onDone(regenerate) | reasoning=${msg.reasoning?.length || 0} content=${msg.content.length} tasks=${msg.tasks?.length || 0}`,
        )
      }
      // showThinking 不再强制覆盖，保持自动收起的状态
      isStreaming.value = false
      abortController = null
      loadSessions()
    },
    (_error) => {
      msg.isStreaming = false
      msg.showRegenerate = true
      isStreaming.value = false
      abortController = null
      if (DEBUG_STREAM) console.debug('[Vue] onError(regenerate):', _error)
    },
  )
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
    await apiDeleteSession(s.id)

    const isCurrent = s.id === currentSessionId.value
    await loadSessions()

    if (isCurrent) {
      currentSessionId.value = ''
      messages.value = []
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
    ElMessage.warning('当前对话已反馈管理员，请勿重复点击～')
  } catch (err: any) {
    if (err?.status === 409) {
      hasFeedback.value = true
      ElMessage.warning('当前对话已反馈管理员，请勿重复点击～')
    }
  }
}

// ==================== 图片预览 ====================
function openImagePreview(src: string) {
  previewImage.value = src
}

function closeImagePreview() {
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

// ==================== 输入框处理 ====================
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !isComposing.value) {
    e.preventDefault()
    sendMessage()
  }
}

function autoResizeInput(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 150) + 'px'
}

// ==================== 滚动处理 ====================
async function scrollToBottom() {
  await nextTick()
  if (messageArea.value) {
    messageArea.value.scrollTop = messageArea.value.scrollHeight
  }
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
  () => messages.value.length,
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
  const firstMsg = messages.value[0]
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
      reasoning: m.reasoning_content || '',
      showThinking: !!(m.reasoning_content),
      isStreaming: false,
      created_at: m.created_at,
    }))

    messages.value = [...olderMsgs, ...messages.value]
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
    await loadFeedbackStatus(list[0].id)
    await nextTick()
    scrollToBottom()
  }
})

onBeforeUnmount(() => {
  stopStreaming()
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
        <button class="btn-new-chat" @click="handleNewChat" :disabled="isStreaming">
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
          :class="{ active: s.id === currentSessionId }"
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
            <div class="chat-item-title">{{ s.title || '新对话' }}</div>
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
        </div>

        <div class="user-info">
          <span class="user-name">{{ currentUser?.username || '' }}</span>
          <div class="user-avatar">{{ (currentUser?.username || '?')[0].toUpperCase() }}</div>
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

        <template v-for="(msg, i) in messages" :key="msg.id || i">
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
              <span v-else>{{ (currentUser?.username || '?')[0].toUpperCase() }}</span>
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
                <!-- 思考过程 -->
                <div
                  v-if="msg.role === 'assistant' && (msg.reasoning || msg.isStreaming || (msg.tasks && msg.tasks.length > 0))"
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
                  <div class="thinking-content">
                    <!-- Skill 任务执行结果 -->
                    <template v-if="msg.tasks && msg.tasks.length > 0">
                      <div v-for="(t, ti) in msg.tasks" :key="ti" class="task-item">
                        <span class="task-badge">{{ t.type }}</span>
                        <span class="task-result">{{ t.result }}</span>
                      </div>
                    </template>
                    <!-- 大模型思考推理过程 -->
                    <div v-if="msg.reasoning" class="reasoning-text">{{ cleanReasoning(msg.reasoning) }}</div>
                    <!-- 占位：等待思考内容 -->
                    <div v-if="msg.isStreaming && !msg.reasoning && (!msg.tasks || msg.tasks.length === 0)" class="thinking-placeholder">
                      正在分析...
                    </div>
                  </div>
                </div>

                <!-- 分隔线 -->
                <div
                  v-if="msg.role === 'assistant' && msg.reasoning && msg.content"
                  class="thinking-divider"
                ></div>

                <!-- 内容（流式时纯文本，完成后 markdown 渲染） -->
                <div
                  v-if="msg.content && msg.isStreaming"
                  class="msg-content"
                  @click="handleMessageContentClick"
                >{{ msg.content }}</div>
                <div
                  v-else-if="msg.content"
                  class="msg-content"
                  v-html="renderMarkdown(msg.content)"
                  @click="handleMessageContentClick"
                ></div>

                <!-- 流式光标 -->
                <span v-if="msg.isStreaming" class="streaming-cursor">▊</span>

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
        <!-- 不满意反馈按钮 -->
        <div class="feedback-row">
          <button
            class="btn-feedback"
            @click="handleFeedback"
          >
            <svg viewBox="0 0 14 14" fill="currentColor">
              <path d="M7 1a.75.75 0 01.75.75v5.035l1.72-1.72a.75.75 0 111.06 1.06l-2.828 2.828a1 1 0 01-1.414 0L3.46 6.125a.75.75 0 111.06-1.06L6.25 6.785V1.75A.75.75 0 017 1zM2.25 7.75a.75.75 0 00-1.5 0v3A1.75 1.75 0 002.5 12.5h9a1.75 1.75 0 001.75-1.75v-3a.75.75 0 00-1.5 0v3a.25.25 0 01-.25.25h-9a.25.25 0 01-.25-.25v-3z"/>
            </svg>
            {{ hasFeedback ? '已反馈' : '不满意本次回答？' }}
          </button>
        </div>

        <!-- 输入区域 -->
        <div class="input-row">
          <div class="input-wrapper-bottom">
            <textarea
              v-model="inputText"
              class="msg-input"
              placeholder="输入您的问题... (Enter 发送, Shift+Enter 换行)"
              rows="1"
              :disabled="isStreaming"
              @keydown="handleKeydown"
              @compositionstart="isComposing = true"
              @compositionend="isComposing = false"
              @input="autoResizeInput"
            ></textarea>
            <button
              class="btn-send"
              :class="{ stop: isStreaming }"
              :disabled="!isStreaming && !inputText.trim()"
              @click="isStreaming ? stopStreaming() : sendMessage()"
              :title="isStreaming ? '停止生成' : '发送'"
            >
              <svg v-if="!isStreaming" viewBox="0 0 18 18" fill="currentColor">
                <path d="M1.5 2.5l15 6.5-15 6.5 3-6.5-3-6.5z"/>
              </svg>
              <svg v-else viewBox="0 0 16 16" fill="currentColor">
                <rect x="3" y="3" width="10" height="10" rx="1"/>
              </svg>
            </button>
          </div>
        </div>
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
.btn-new-chat:disabled { background: var(--color-text-disabled); cursor: not-allowed; transform: none; }
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
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
  gap: 8px;
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
.thinking-content {
  padding: 10px 12px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  line-height: 20px;
  max-height: 200px;
  overflow-y: auto;
  border-top: 1px solid var(--color-border-light);
}
.thinking-block.collapsed .thinking-content {
  display: none;
}
.thinking-content::-webkit-scrollbar { width: 3px; }
.thinking-content::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 2px;
}

/* 任务执行项 */
.task-item {
  margin-bottom: 8px;
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
  color: var(--color-text-secondary);
  word-break: break-word;
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

/* ==================== 底部区域 ==================== */
.bottom-area {
  background: var(--color-bg-card);
  border-top: 1px solid var(--color-border-light);
  padding: 16px 24px;
  flex-shrink: 0;
}

.feedback-row {
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
}

.btn-feedback {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 16px;
  font-size: 13px;
  color: var(--color-text-tertiary);
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
}
.btn-feedback:hover {
  color: var(--color-warning);
  border-color: var(--color-warning);
  background: #FFF8EC;
}
.btn-feedback svg { width: 14px; height: 14px; }

.input-row { position: relative; }
.input-wrapper-bottom { position: relative; }

.msg-input {
  width: 100%;
  min-height: 64px;
  max-height: 150px;
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
  right: 6px;
  bottom: 6px;
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
