import { marked } from 'marked'

export interface RetrievalImage { alt: string; path: string; source?: string }
export interface TaskInfo {
  type: string; result: string; query?: string; hitText?: string; images?: RetrievalImage[]
}
export interface ThinkingStep { kind: 'reasoning' | 'task'; text?: string; clean?: string; task?: TaskInfo }
export interface UIMessage {
  id?: number; role: 'user' | 'assistant'; content: string
  attachments?: any[]
  reasoning?: string; steps?: ThinkingStep[]; showThinking?: boolean
  isStreaming?: boolean; showRegenerate?: boolean; error?: string
  created_at?: number; _renderedHtml?: string; _stepBreak?: boolean
}

const renderer = new marked.Renderer()
const originalImage = renderer.image.bind(renderer)
let _streaming = false
export function setStreamingRender(v: boolean) { _streaming = v }

renderer.image = function (token: any): string {
  let href = typeof token === 'string' ? token : (token?.href || '')
  const text = typeof token === 'string' ? '' : (token?.text || '')
  if (href.startsWith('../assets/')) href = href.replace(/^\.\.\//, '/')
  const html = originalImage(token as any)
  if (!_streaming) return html
  return html.replace(/<img([^>]*?)>/, () =>
    `<span class="img-stream-placeholder" data-src="${href}" data-alt="${text}">[图片加载中…]</span>`)
}
marked.setOptions({ breaks: true, gfm: true, renderer })

export function renderMarkdown(text: string): string {
  try { return marked.parse(text || '') as string } catch { return text || '' }
}

const RENDER_THROTTLE_MS = 150
const timers = new WeakMap<object, number>()

export function syncDerived(msg: UIMessage) {
  msg._renderedHtml = renderMarkdown(msg.content)
  for (const st of msg.steps || []) {
    if (st.kind === 'reasoning') st.clean = cleanReasoning(st.text || '')
  }
}

export function scheduleRender(msg: UIMessage) {
  const key = msg as unknown as object
  const prev = timers.get(key)
  if (prev) clearTimeout(prev)
  if (!msg.isStreaming) { syncDerived(msg); return }
  _streaming = true
  const timer = window.setTimeout(() => { timers.delete(key); syncDerived(msg) }, RENDER_THROTTLE_MS)
  timers.set(key, timer)
}

export function cleanReasoning(text: string): string {
  return (text || '').replace(/<\/?think>/gi, '').replace(/<THINK_V2>/gi, '').trim()
}

export function parseRetrievalResult(result: string): { text: string; images: RetrievalImage[]; source?: string } {
  const marker = '### 命中图片（可选）'
  const idx = (result || '').indexOf(marker)
  if (idx === -1) return { text: result || '', images: [] }
  const text = result.slice(0, idx).trim()
  const tail = result.slice(idx + marker.length)
  const images: RetrievalImage[] = []
  const re = /!\[([^\]]*)\]\(([^)]+)\)/g
  let m: RegExpExecArray | null
  while ((m = re.exec(tail))) images.push({ alt: m[1], path: m[2] })
  const sm = tail.match(/来源[：:]\s*([^\n]+)/)
  return { text, images, source: sm ? sm[1].trim() : undefined }
}

export function makeTask(type: string, result: string, query: string): TaskInfo {
  const task: TaskInfo = { type, result, query }
  if (type === 'knowledge_retrieval') {
    const p = parseRetrievalResult(result)
    task.hitText = p.text; task.images = p.images
  }
  return task
}

export function appendReasoningStep(msg: UIMessage, text: string) {
  if (!text) return
  msg.steps = msg.steps || []
  const last = msg.steps[msg.steps.length - 1]
  if (last && last.kind === 'reasoning' && !msg._stepBreak) { last.text = (last.text || '') + text; return }
  msg.steps.push({ kind: 'reasoning', text })
  msg._stepBreak = false
}
export function breakReasoningStep(msg: UIMessage) { msg._stepBreak = true }
export function appendTaskStep(msg: UIMessage, task: TaskInfo) {
  msg.steps = msg.steps || []
  msg.steps.push({ kind: 'task', task })
  msg._stepBreak = true
}

export function buildHistorySteps(m: any): ThinkingStep[] {
  if (Array.isArray(m.steps) && m.steps.length) {
    return m.steps.map((s: any) => s.kind === 'task'
      ? { kind: 'task', task: { type: s.type || '', result: s.result || '', query: s.query || '' } }
      : { kind: 'reasoning', text: s.text || '' })
  }
  const steps: ThinkingStep[] = []
  if (m.reasoning_content) steps.push({ kind: 'reasoning', text: m.reasoning_content })
  for (const t of m.tasks || []) steps.push({ kind: 'task', task: { type: t.type || '', result: t.result || '', query: t.query || '' } })
  return steps
}

function pad(n: number) { return String(n).padStart(2, '0') }
export function formatTime(ts?: number): string {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
export function formatMessageTime(ts?: number): string {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
export function showTimeDivider(prev: UIMessage | undefined, cur: UIMessage): boolean {
  if (!prev || !prev.created_at || !cur.created_at) return false
  return cur.created_at - prev.created_at > 300
}
export function truncatePreview(s: string): string {
  if (!s) return ''
  return s.length > 50 ? s.slice(0, 50) + '…' : s
}
