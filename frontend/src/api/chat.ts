import { authFetch } from './auth'

export interface ChatMessage {
  id?: number
  role: 'user' | 'assistant' | 'system'
  content: string
  reasoning_content?: string
  created_at?: number
}

export interface Session {
  id: string
  title: string
  status: string
  user_id?: number | null
  last_message?: string
  created_at: number
  updated_at: number
}

export interface ListSessionsResponse {
  sessions: Session[]
  total: number
  has_more: boolean
}

export interface ListMessagesResponse {
  session_id: string
  messages: ChatMessage[]
  has_more: boolean
}

const BASE = '/api'

// ==================== DEBUG 开关 ====================
const DEBUG_STREAM = true

export async function listSessions(
  limit: number = 10,
  offset: number = 0,
): Promise<ListSessionsResponse> {
  const resp = await authFetch(`${BASE}/sessions?limit=${limit}&offset=${offset}`)
  return await resp.json()
}

export async function getSessionMessages(
  sessionId: string,
  limit: number = 50,
  beforeId?: number,
): Promise<ListMessagesResponse> {
  let url = `${BASE}/sessions/${sessionId}/messages?limit=${limit}`
  if (beforeId) {
    url += `&before_id=${beforeId}`
  }
  const resp = await authFetch(url)
  return await resp.json()
}

export async function deleteSession(sessionId: string): Promise<void> {
  await authFetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
}

export async function updateSessionTitle(sessionId: string, title: string): Promise<void> {
  await authFetch(`${BASE}/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export async function createSession(): Promise<string> {
  const resp = await authFetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: '', message: '', new_session: true }),
  })
  return resp.headers.get('X-Session-Id') || ''
}

export async function submitFeedback(sessionId: string): Promise<{ ok: boolean; message: string }> {
  const resp = await authFetch(`${BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!resp.ok) {
    const errData = await resp.json().catch(() => ({}))
    const error: any = new Error(errData.detail || 'Feedback failed')
    error.status = resp.status
    throw error
  }
  return await resp.json()
}

export async function checkFeedback(sessionId: string): Promise<{ has_feedback: boolean }> {
  const resp = await authFetch(`${BASE}/feedback/check?session_id=${sessionId}`)
  return await resp.json()
}

/**
 * 强制浏览器渲染一帧。
 * 先通过 setTimeout(0) 让出到 macrotask 队列（Vue 的微任务刷新得以执行），
 * 再通过 requestAnimationFrame 等待浏览器完成绘制帧，
 * 确保页面呈现「逐 token 弹出」的流式效果。
 */
function forceRenderFrame(): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(() => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => resolve())
      })
    }, 0)
  })
}

export function streamChat(
  sessionId: string,
  message: string,
  onContent: (text: string) => void,
  onReasoning: (text: string) => void,
  onTask: (type: string, result: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
): AbortController {
  const controller = new AbortController()
  const token = localStorage.getItem('auth_token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // 调试用计数器
  let contentTokenCount = 0
  let reasoningTokenCount = 0
  let taskCount = 0

  fetch(`${BASE}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ session_id: sessionId, message, new_session: false }),
    signal: controller.signal,
  }).then(async (resp) => {
    if (resp.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user_info')
      window.location.href = '/login'
      return
    }
    if (!resp.ok) {
      onError(`HTTP ${resp.status}`)
      return
    }
    const reader = resp.body?.getReader()
    if (!reader) {
      onError('No response body')
      return
    }
    const decoder = new TextDecoder()
    let buffer = ''
    let eventLines: string[] = []

    function flushEvent(): string {
      if (eventLines.length === 0) return ''
      let eventType = ''
      let dataStr = ''

      for (const ln of eventLines) {
        if (ln.startsWith('event: ')) {
          eventType = ln.slice(7).trim()
        } else if (ln.startsWith('data: ')) {
          dataStr = ln.slice(6).trim()
        }
      }
      eventLines = []

      if (!eventType && !dataStr) return ''
      if (dataStr === '{}') {
        if (eventType === 'done') {
          if (DEBUG_STREAM) {
            console.debug(
              `[SSE] ✅ done | reasoning tokens: ${reasoningTokenCount}, content tokens: ${contentTokenCount}, tasks: ${taskCount}`,
            )
          }
          onDone()
        }
        return eventType
      }

      try {
        const data = dataStr ? JSON.parse(dataStr) : {}
        switch (eventType) {
          case 'content':
            contentTokenCount++
            if (DEBUG_STREAM) {
              const preview = (data.content || '').substring(0, 40).replace(/\n/g, '\\n')
              console.debug(`[SSE] 📝 content #${contentTokenCount}: "${preview}"`)
            }
            onContent(data.content || '')
            break
          case 'reasoning':
            reasoningTokenCount++
            if (DEBUG_STREAM) {
              const preview = (data.reasoning || data.content || '').substring(0, 40).replace(/\n/g, '\\n')
              console.debug(`[SSE] 💭 reasoning #${reasoningTokenCount}: "${preview}"`)
            }
            onReasoning(data.content || '')
            break
          case 'task':
            taskCount++
            if (DEBUG_STREAM) {
              console.debug(`[SSE] 🔧 task #${taskCount}: type=${data.type}`)
            }
            onTask(data.type || '', data.result || '')
            break
          case 'error':
            onError(data.content || 'Unknown error')
            break
          case 'done':
            onDone()
            break
          case 'warning':
            console.warn('Warning:', data.content)
            break
        }
      } catch {
        // skip malformed
      }
      return eventType
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line === '') {
          const eventType = flushEvent()
          // content / reasoning 事件后强制渲染一帧，保证逐 token 流式显示
          if (eventType === 'content' || eventType === 'reasoning') {
            if (DEBUG_STREAM) {
              console.debug(`[SSE] ⏸️  yield frame after ${eventType}`)
            }
            await forceRenderFrame()
          }
        } else {
          eventLines.push(line)
        }
      }
    }
    // 处理残留 buffer
    if (buffer !== '') {
      eventLines.push(buffer)
    }
    flushEvent()
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      onError(err.message)
    }
  })

  return controller
}
