import { ref, computed, reactive, watch } from 'vue'
import {
  streamAdminChat, getAdminSessionMessages, createAdminSession,
  applyContextBatch, discardContextBatch, getContextBatches,
} from '../api/admin'
import type { UIMessage } from '../components/messageUtils'
import {
  scheduleRender, makeTask, appendReasoningStep, breakReasoningStep, appendTaskStep, buildHistorySteps,
} from '../components/messageUtils'

export interface ContextChange {
  /** 批次数字主键：确认/取消接口按 id 调用（batch_no 只是展示用） */
  batch_id?: number
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

// 抽屉关闭会卸载组件，用 localStorage 记住「已打开的会话」，
// 再次打开时恢复而不是每次新建一个空会话。
const STORAGE_KEY = 'admin_chat_open_tabs'

interface SavedTab { sessionId: string; title?: string; active?: boolean }

export function useMaintenanceChat() {
  const tabs = ref<ChatTab[]>([])
  const activeTabId = ref('')
  const visible = ref(false)
  const controllers = new Map<string, AbortController>()

  const activeTab = computed(() => tabs.value.find(t => t.id === activeTabId.value) || null)

  function makeTabId() { return `tab_${Date.now()}_${Math.random().toString(36).slice(2, 8)}` }

  // 恢复期间不写存储，避免把「只恢复了一半」的列表覆盖掉原始记录
  let restoring = false

  function persistTabs() {
    if (restoring) return
    try {
      const saved: SavedTab[] = tabs.value.map(t => ({
        sessionId: t.sessionId,
        title: t.titleStatus === 'ready' ? t.title : '',
        active: t.id === activeTabId.value,
      }))
      localStorage.setItem(STORAGE_KEY, JSON.stringify(saved))
    } catch { /* 隐私模式等存储不可用时忽略 */ }
  }

  // 只监听 Tab 元信息（会话号/标题/激活态），避免消息流式更新频繁写存储
  watch(
    () => JSON.stringify(tabs.value.map(t => [
      t.sessionId,
      t.titleStatus === 'ready' ? t.title : '',
      t.id === activeTabId.value,
    ])),
    persistTabs,
  )

  /** 恢复上次未关闭的会话 Tab；返回是否恢复了至少一个 */
  async function restoreTabs(): Promise<boolean> {
    let saved: SavedTab[] = []
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      const parsed = raw ? JSON.parse(raw) : []
      saved = Array.isArray(parsed) ? parsed : []
    } catch { saved = [] }
    if (!saved.length) return false

    restoring = true
    try {
      for (const item of saved) {
        if (!item?.sessionId) continue
        const tab = await openTab(item.sessionId, item.title || '新对话')
        // 会话已被删除或后端不可用：丢弃该 Tab，避免留下一个空白对话
        if (!tab.messages.length) closeTab(tab)
      }
      if (!tabs.value.length) return false

      const activeSaved = saved.find(s => s.active)?.sessionId
      const active = tabs.value.find(t => t.sessionId === activeSaved)
      activeTabId.value = (active || tabs.value[tabs.value.length - 1]).id
      return true
    } finally {
      restoring = false
      persistTabs()
    }
  }

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
    await restorePendingChanges(tab)
    return tab
  }

  async function loadHistory(tab: ChatTab) {
    try {
      const data: any = await getAdminSessionMessages(tab.sessionId, 50)
      const msgs: UIMessage[] = (data.data?.messages || [])
        .filter((m: any) => !(m.role === 'user' && m.content.startsWith('<task_result>')))
        .map((m: any) => {
          const msg = reactive<UIMessage>({
            id: m.id, role: m.role, content: m.content, created_at: m.created_at,
            reasoning: m.reasoning_content || '', showThinking: false,
          })
          msg.steps = buildHistorySteps(m)
          msg.showThinking = !!(msg.steps && msg.steps.length)
          scheduleRender(msg)
          return msg
        })
      // 必须写回响应式代理：直接给原始 tab 对象赋值不会触发视图更新，
      // 会导致欢迎语/历史消息要等到下一次交互（如输入内容）才渲染出来。
      const live = tabs.value.find(t => t.id === tab.id)
      if (live) live.messages = msgs
      else tab.messages = msgs
    } catch { /* 历史加载失败不阻塞打开 Tab */ }
  }

  /** 还原该会话仍 pending 的变更草稿：重开抽屉/从历史打开时也能看到确认条 */
  async function restorePendingChanges(tab: ChatTab) {
    try {
      const httpResp = await getContextBatches('pending', 10, tab.sessionId)
      if (!httpResp.ok) return
      const resp: any = await httpResp.json()
      if (!resp?.ok) return
      const batches: any[] = resp.data?.batches || []
      const changes: ContextChange[] = []
      for (const b of batches) {
        const items: any[] = b.items || []
        const count = b.item_count || items.length
        for (const it of items) {
          changes.push({
            batch_id: b.id,
            batch_no: b.batch_no,
            item_index: it.item_index ?? 0,
            item_count: count,
            op: it.action || 'update',
            target: it.target || '',
            summary: it.summary || b.summary || '',
            diff: it.diff || '',
          })
        }
      }
      if (!changes.length) return
      const live = tabs.value.find(t => t.id === tab.id)
      if (live) live.changes = changes
      else tab.changes = changes
    } catch { /* 还原草稿失败不影响对话 */ }
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
    const groups = new Map<string, {
      batch_id?: number; batch_no: string; item_count: number; changes: ContextChange[]
    }>()
    for (const ch of tab.changes) {
      if (!groups.has(ch.batch_no)) {
        groups.set(ch.batch_no, {
          batch_id: ch.batch_id, batch_no: ch.batch_no,
          item_count: ch.item_count, changes: [],
        })
      }
      groups.get(ch.batch_no)!.changes.push(ch)
    }
    return [...groups.values()]
  }

  function send(tab: ChatTab, text: string) {
    if (tab.streaming) return
    const now = Date.now() / 1000
    tab.messages.push({ role: 'user', content: text, created_at: now, showThinking: false })
    // 用 reactive 包装：否则后续 content/reasoning 的增量写入不会触发渲染
    const assistant = reactive<UIMessage>({
      role: 'assistant', content: '', reasoning: '', isStreaming: true,
      steps: [], showThinking: true, created_at: now,
    })
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
          batch_id: data.batch_id, batch_no: data.batch_no, item_index: data.item_index,
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

  /**
   * 确认/取消整个批次。
   * 注意：后端接口路径参数是批次的数字主键 id（不是 batch_no 字符串），
   * 之前用 Number(batch_no) 会得到 NaN，请求必然 422 → 前端提示「操作失败」。
   */
  async function confirmBatch(
    tab: ChatTab, batchId: number | undefined, batchNo: string, action: 'apply' | 'discard',
  ): Promise<{ ok: boolean; status: number }> {
    if (!batchId || !Number.isFinite(batchId)) return { ok: false, status: 0 }
    const resp = action === 'apply'
      ? await applyContextBatch(batchId)
      : await discardContextBatch(batchId)
    if (resp.ok) {
      if (action === 'apply') {
        tab.changes = tab.changes.map(c => c.batch_no === batchNo
          ? { ...c, op: 'applied' } : c)
      } else {
        tab.changes = tab.changes.filter(c => c.batch_no !== batchNo)
      }
    }
    return { ok: resp.ok, status: resp.status }
  }

  function dispose() {
    controllers.forEach(c => c.abort())
    controllers.clear()
  }

  return {
    tabs, activeTabId, activeTab, visible,
    openTab, createTab, restoreTabs, activate, send, stop, closeTab, confirmBatch,
    getBatchGroups, dispose, skipLoad: false,
  }
}
