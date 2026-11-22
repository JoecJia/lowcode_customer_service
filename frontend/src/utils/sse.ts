/** 通用 SSE 解析：把 ReadableStream 逐事件回调给调用方。
 *  供前台（api/chat.ts）与后台（api/admin.ts）共用，见开发文档 §6.3。
 */
export interface SSEHandlers {
  onEvent: (eventType: string, data: any) => void
  onError?: (error: string) => void
  onUnauthorized?: () => void
}

export async function consumeSSE(
  resp: Response,
  handlers: SSEHandlers,
): Promise<void> {
  if (resp.status === 401) {
    handlers.onUnauthorized?.()
    return
  }
  if (!resp.ok) {
    handlers.onError?.(`HTTP ${resp.status}`)
    return
  }
  const reader = resp.body?.getReader()
  if (!reader) {
    handlers.onError?.('No response body')
    return
  }
  const decoder = new TextDecoder()
  let buffer = ''
  let eventLines: string[] = []

  function flushEvent() {
    if (eventLines.length === 0) return
    let eventType = ''
    let dataStr = ''
    for (const ln of eventLines) {
      if (ln.startsWith('event:')) eventType = ln.slice(6).trim()
      else if (ln.startsWith('data:')) dataStr = ln.slice(5).trim()
    }
    eventLines = []
    if (!eventType && !dataStr) return
    let data: any = {}
    if (dataStr && dataStr !== '{}') {
      try { data = JSON.parse(dataStr) } catch { return }
    }
    handlers.onEvent(eventType, data)
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line === '') flushEvent()
      else eventLines.push(line)
    }
  }
  if (buffer !== '') eventLines.push(buffer)
  flushEvent()
}
