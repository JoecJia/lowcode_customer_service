import { ref, computed } from 'vue'
import {
  streamAdminChat, getAdminSessionMessages, createAdminSession,
  applyContextBatch, discardContextBatch,
} from '../api/admin'
import type { UIMessage } from '../components/messageUtils'
import {
  scheduleRender, makeTask, appendReasoningStep, breakReasoningStep, appendTaskStep, buildHistorySteps,
} from '../components/messageUtils'

export interface ContextChange {
  batch_no: string
  item_index: number
  item_count: number
  op: string
  target: string
  summary: string
  diff: string
}

export interface ChatTab {
  id: string
  sessionId: string
  title: string
  titleStatus: 'pending' | 'ready'
  messages: UIMessage[]
  changes: ContextChange[]
  streaming: boolean
  error?: string
  skipLoad?: boolean
}

export function useMaintenanceChat() {
  const tabs = ref<ChatTab[]>([])
  const activeTabId = ref('')
  const visible = ref(false)
  const controllers = new Map<string, AbortController>()

  const activeTab = computed(() => tabs.value.find(t => t.id === activeTabId.value) || null)

  function makeTabId() { return `tab_${Date.now()}_${Math.random().toString(36).slice(2, 8)}` }

  async function openTab(sessionId: string, title = '新对话') {
    const existed = tabs.value.find(t => t.sessionId === sessionId)
    if (existed) { activeTabId.value = existed.id; return existed }
    const tab: ChatTab = {
      id: makeTabId(), sessionId, title,
      titleStatus: title && title !== '新对话' ? 'ready' : 'pending',
      messages: [], changes: [], streaming: false,
    }
    tabs.value.push(tab)
    activeTabId.value = tab.id
    await loadHistory(tab)
    return tab
  }

  async function loadHistory(tab: ChatTab) {
    try {
      const data: any = await getAdminSessionMessages(tab.sessionId, 50)
      const msgs: UIMessage[] = (data.data?.messages || [])
        .filter((m: any) => !(m.role === 'user' && m.content.startsWith('<task_result>')))
        .map((m: any) => {
          const msg: UIMessage = {
            id: m.id, role: m.role, content: m.content, created_at: m.created_at,
            reasoning: m.reasoning_content || '', showThinking: false,
          }
          msg.steps = buildHistorySteps(m)
          msg.showThinking = !!(msg.steps && msg.steps.length)
          scheduleRender(msg)
          return msg
        })
      tab.messages = msgs
    } catch { /* 历史加载失败不阻塞打开 Tab */ }
  }

  async function createTab() {
    const resp = await createAdminSession()
    const sid = resp.data?.session_id
    if (!sid) return
    const tab: ChatTab = {
      id: makeTabId(), sessionId: sid, title: '新对话', titleStatus: 'pending',
      messages: [], changes: [], streaming: false,
    }
    tabs.value.push(tab)
    activeTabId.value = tab.id
    // 新会话已在后端写入欢迎语，加载以回显（见 session_service.create_session）
    await loadHistory(tab)
    return tab
  }

  function activate(id: string) { activeTabId.value = id }

  function getBatchGroups(tab: ChatTab) {
    const groups = new Map<string, { batch_no: string; item_count: number; changes: ContextChange[] }>()
    for (const ch of tab.changes) {
      if (!groups.has(ch.batch_no)) {
        groups.set(ch.batch_no, { batch_no: ch.batch_no, item_count: ch.item_count, changes: [] })
      }
      groups.get(ch.batch_no)!.changes.push(ch)
    }
    return [...groups.values()]
  }

  function send(tab: ChatTab, text: string) {
    if (tab.streaming) return
    const now = Date.now() / 1000
    tab.messages.push({ role: 'user', content: text, created_at: now, showThinking: false })
    const assistant: UIMessage = {
      role: 'assistant', content: '', reasoning: '', isStreaming: true,
      steps: [], showThinking: true, created_at: now,
    }
    tab.messages.push(assistant)
    scheduleRender(assistant)
    tab.streaming = true
    tab.error = undefined

    const controller = streamAdminChat(tab.sessionId, text, {
      onContent: (chunk) => {
        assistant.content += chunk
        assistant.showThinking = false
        breakReasoningStep(assistant); scheduleRender(assistant)
      },
      onReasoning: (chunk) => {
        assistant.reasoning = (assistant.reasoning || '') + chunk
        appendReasoningStep(assistant, chunk); scheduleRender(assistant)
      },
      onTask: (type, result, query) => {
        appendTaskStep(assistant, makeTask(type, result, query)); scheduleRender(assistant)
      },
      onChange: (data) => {
        // 同批次同 item 覆盖（对话内调整），不堆叠
        const idx = tab.changes.findIndex(
          c => c.batch_no === data.batch_no && c.item_index === data.item_index,
        )
        const change: ContextChange = {
          batch_no: data.batch_no, item_index: data.item_index,
          item_count: data.item_count || 1, op: data.op || 'update',
          target: data.target || '', summary: data.summary || '', diff: data.diff || '',
        }
        if (idx >= 0) tab.changes[idx] = change
        else tab.changes.push(change)
      },
      onTitle: (title) => {
        if (tab.titleStatus === 'pending' && title) { tab.title = title; tab.titleStatus = 'ready' }
      },
      onDone: () => {
        assistant.isStreaming = false; tab.streaming = false
        controllers.delete(tab.id)
      },
      onError: (err) => {
        assistant.isStreaming = false; tab.streaming = false
        assistant.error = err || '请求失败，请重试'
        tab.error = err
        controllers.delete(tab.id)
      },
    })
    controllers.set(tab.id, controller)
  }

  function stop(tab: ChatTab) {
    const c = controllers.get(tab.id)
    if (c) c.abort()
    tab.streaming = false
    const last = tab.messages[tab.messages.length - 1]
    if (last?.isStreaming) last.isStreaming = false
    controllers.delete(tab.id)
  }

  function closeTab(tab: ChatTab) {
    const c = controllers.get(tab.id)
    if (c) c.abort()
    controllers.delete(tab.id)
    tabs.value = tabs.value.filter(t => t.id !== tab.id)
    if (activeTabId.value === tab.id) {
      activeTabId.value = tabs.value.length ? tabs.value[tabs.value.length - 1].id : ''
    }
  }

  async function confirmBatch(tab: ChatTab, batchNo: string, action: 'apply' | 'discard') {
    const resp = action === 'apply'
      ? await applyContextBatch(Number(batchNo))
      : await discardContextBatch(Number(batchNo))
    if (resp.ok) {
      if (action === 'apply') {
        tab.changes = tab.changes.map(c => c.batch_no === batchNo
          ? { ...c, op: 'applied' } : c)
      } else {
        tab.changes = tab.changes.filter(c => c.batch_no !== batchNo)
      }
    }
    return resp
  }

  function dispose() {
    controllers.forEach(c => c.abort())
    controllers.clear()
  }

  return {
    tabs, activeTabId, activeTab, visible,
    openTab, createTab, activate, send, stop, closeTab, confirmBatch,
    getBatchGroups, dispose, skipLoad: false,
  }
}
