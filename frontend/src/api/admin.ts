const BASE = '/api/admin'

function getAdminAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('admin_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

export async function adminAuthFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = getAdminAuthHeaders()
  const resp = await fetch(url, {
    ...options,
    headers: { ...headers, ...(options.headers || {}) },
  })
  if (resp.status === 401) {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_info')
    window.location.href = '/admin/login'
  }
  return resp
}

// 反馈
export async function getFeedbacks(params: Record<string, string>) {
  const qs = new URLSearchParams(params).toString()
  return adminAuthFetch(`${BASE}/feedbacks?${qs}`)
}

export async function getFeedbackDetail(id: number) {
  return adminAuthFetch(`${BASE}/feedbacks/${id}`)
}

export async function resolveFeedback(id: number, qa_pairs: { question: string; answer: string }[]) {
  return adminAuthFetch(`${BASE}/feedbacks/${id}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ qa_pairs }),
  })
}

export async function markFeedbackNoNeed(id: number) {
  return adminAuthFetch(`${BASE}/feedbacks/${id}/no-need`, {
    method: 'POST',
  })
}

// Agent 配置
export async function getAgentConfigTree() {
  return adminAuthFetch(`${BASE}/agent-config/tree`)
}

export async function getAgentConfigFile(path: string) {
  const qs = new URLSearchParams({ path }).toString()
  return adminAuthFetch(`${BASE}/agent-config/file?${qs}`)
}

// 账号管理
export async function getAccounts(params: Record<string, string>) {
  const qs = new URLSearchParams(params).toString()
  return adminAuthFetch(`${BASE}/accounts?${qs}`)
}

export async function createAccount(data: Record<string, unknown>) {
  return adminAuthFetch(`${BASE}/accounts`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateAccountPassword(userId: number, password: string) {
  return adminAuthFetch(`${BASE}/accounts/${userId}/password`, {
    method: 'PATCH',
    body: JSON.stringify({ password }),
  })
}

export async function updateAccountPermissions(userId: number, can_chat: number, can_admin: number) {
  return adminAuthFetch(`${BASE}/accounts/${userId}/permissions`, {
    method: 'PATCH',
    body: JSON.stringify({ can_chat, can_admin }),
  })
}

// ====== 后台维护助手会话 ======

export interface AdminSession {
  id: string
  title: string
  scope: string
  user_id?: number | null
  last_message?: string
  created_at: number
  updated_at: number
}

export async function listAdminSessions(limit = 20, offset = 0) {
  const resp = await adminAuthFetch(`${BASE}/sessions?limit=${limit}&offset=${offset}`)
  return await resp.json() as { ok: boolean; data: { sessions: AdminSession[]; total: number; has_more: boolean } }
}

export async function createAdminSession() {
  const resp = await adminAuthFetch(`${BASE}/sessions`, { method: 'POST' })
  return await resp.json() as { ok: boolean; data: { session_id: string } }
}

export async function getAdminSessionMessages(sessionId: string, limit = 50, beforeId?: number) {
  const qs = new URLSearchParams({ limit: String(limit) })
  if (beforeId) qs.set('before_id', String(beforeId))
  const resp = await adminAuthFetch(`${BASE}/sessions/${sessionId}/messages?${qs}`)
  return await resp.json()
}

export async function renameAdminSession(sessionId: string, title: string) {
  return adminAuthFetch(`${BASE}/sessions/${sessionId}`, {
    method: 'PATCH', body: JSON.stringify({ title }),
  })
}

export async function deleteAdminSession(sessionId: string) {
  return adminAuthFetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
}

/** 后台对话 SSE。回调式，返回 AbortController。change 事件驱动变更卡片。 */
export function streamAdminChat(
  sessionId: string,
  message: string,
  handlers: {
    onContent: (text: string) => void
    onReasoning: (text: string) => void
    onTask: (type: string, result: string, query: string) => void
    onChange: (data: any) => void
    onTitle: (title: string) => void
    onDone: () => void
    onError: (error: string) => void
  },
): AbortController {
  const controller = new AbortController()
  const token = localStorage.getItem('admin_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  fetch(`${BASE}/chat`, {
    method: 'POST', headers,
    body: JSON.stringify({ session_id: sessionId, message }),
    signal: controller.signal,
  }).then(async (resp) => {
    if (resp.status === 401) {
      localStorage.removeItem('admin_token'); localStorage.removeItem('admin_info')
      window.location.href = '/admin/login'; return
    }
    if (!resp.ok) { handlers.onError(`HTTP ${resp.status}`); return }
    const reader = resp.body?.getReader()
    if (!reader) { handlers.onError('No response body'); return }
    const decoder = new TextDecoder()
    let buffer = ''
    let eventLines: string[] = []
    const flush = () => {
      if (!eventLines.length) return
      let type = '', dataStr = ''
      for (const ln of eventLines) {
        if (ln.startsWith('event:')) type = ln.slice(6).trim()
        else if (ln.startsWith('data:')) dataStr = ln.slice(5).trim()
      }
      eventLines = []
      if (!type && !dataStr) return
      let data: any = {}
      if (dataStr && dataStr !== '{}') { try { data = JSON.parse(dataStr) } catch { return } }
      switch (type) {
        case 'content': handlers.onContent(data.content || ''); break
        case 'reasoning': handlers.onReasoning(data.content || ''); break
        case 'task': handlers.onTask(data.type || '', data.result || '', data.query || ''); break
        case 'change': handlers.onChange(data); break
        case 'title': handlers.onTitle(data.title || ''); break
        case 'done': handlers.onDone(); break
        case 'error': handlers.onError(data.content || 'Unknown error'); break
        case 'warning': console.warn('Warning:', data.content); break
      }
    }
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) { if (line === '') flush(); else eventLines.push(line) }
    }
    if (buffer !== '') eventLines.push(buffer)
    flush()
  }).catch((err) => { if (err.name !== 'AbortError') handlers.onError(err.message) })
  return controller
}

// ====== Context 批次 ======

export interface ContextBatchItem {
  target: string
  action: string
  new_hash: string | null
  backup_path?: string
  item_index?: number
  summary: string
}
export interface ContextBatch {
  id: number
  batch_no: string
  session_id: string
  session_title?: string
  operator: string
  status: 'pending' | 'applied' | 'discarded' | 'rolled_back'
  item_count: number
  summary: string
  restored_from: number | null
  created_at: number
  applied_at: number | null
  items: ContextBatchItem[]
}

/** status 传 'applied,rolled_back'（逗号分隔多状态） */
export async function getContextBatches(status: string, limit = 50) {
  const qs = new URLSearchParams({ status, limit: String(limit) })
  return adminAuthFetch(`${BASE}/context/batches?${qs}`)
}
export async function applyContextBatch(batchId: number) {
  return adminAuthFetch(`${BASE}/context/batches/${batchId}/apply`, { method: 'POST' })
}
export async function discardContextBatch(batchId: number) {
  return adminAuthFetch(`${BASE}/context/batches/${batchId}/discard`, { method: 'POST' })
}
export async function rollbackContextBatch(batchId: number) {
  return adminAuthFetch(`${BASE}/context/batches/${batchId}/rollback`, { method: 'POST' })
}
