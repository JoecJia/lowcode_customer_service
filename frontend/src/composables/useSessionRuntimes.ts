import { computed, reactive } from 'vue'

export interface SessionRuntime<TMessage> {
  sessionId: string
  /** 是否正在生成；唯一权威来源 */
  generating: boolean
  /** 当前流的控制器；generating=false 时应为 null */
  controller: AbortController | null
  /** 当前流正在写入的消息引用，停止时精确定位，不靠数组末尾猜测 */
  streamingMessage: TMessage | null
  /** 该会话消息缓存（含流式半成品） */
  messages: TMessage[]
  /** 是否已从后端加载过历史消息 */
  initialized: boolean
  /** 该会话独立的输入草稿 */
  draft: string
  /** 该会话消息区滚动位置 */
  scrollTop: number
  /** 最近一次生成错误；非空时展示失败态 */
  error: string | null
  /** 生成完成后用户未切换到该会话，展示未读标识；切换进入后清除 */
  unread: boolean
}

export function useSessionRuntimes<TMessage>() {
  const runtimes = reactive<Record<string, SessionRuntime<TMessage>>>({})

  function getRuntime(sid: string): SessionRuntime<TMessage> | undefined {
    return runtimes[sid]
  }

  /** 获取或创建运行时（幂等） */
  function ensureRuntime(sid: string): SessionRuntime<TMessage> {
    if (!runtimes[sid]) {
      runtimes[sid] = {
        sessionId: sid,
        generating: false,
        controller: null,
        streamingMessage: null,
        messages: [],
        initialized: false,
        draft: '',
        scrollTop: 0,
        error: null,
        unread: false,
      }
    }
    return runtimes[sid]
  }

  /**
   * 回调守卫：运行时存在 + 仍生成中 + 控制器未更换 + 未 abort 四者同时满足才允许写入。
   * 防止已删除会话、已停止流、迟到的 error 事件污染其他会话数据。
   */
  function isActiveCallback(sid: string, controller: AbortController): boolean {
    const rt = runtimes[sid]
    return !!rt
      && rt.generating
      && rt.controller === controller
      && !controller.signal.aborted
  }

  /** 开始生成；该会话已在生成时返回 false（同会话防并发） */
  function markGenerating(
    sid: string,
    controller: AbortController,
    streamingMessage: TMessage,
  ): boolean {
    const rt = ensureRuntime(sid)
    if (rt.generating) return false
    rt.generating = true
    rt.controller = controller
    rt.streamingMessage = streamingMessage
    rt.error = null
    return true
  }

  /** 结束生成；幂等。error 非空时进入失败态 */
  function finishGenerating(
    sid: string,
    result: { success?: boolean; error?: string | null; stopped?: boolean } = {},
  ): void {
    const rt = runtimes[sid]
    if (!rt || !rt.generating) return
    rt.generating = false
    rt.controller = null
    if (result.error) rt.error = result.error
    else if (!result.stopped) rt.error = null
    rt.streamingMessage = null
  }

  /** 生成完成时标记未读（仅当用户当前不在该会话时由调用方决定） */
  function markUnread(sid: string): void {
    const rt = runtimes[sid]
    if (rt) rt.unread = true
  }

  /** 切换到会话后清除未读 */
  function markRead(sid: string): void {
    const rt = runtimes[sid]
    if (rt) rt.unread = false
  }

  /** 中断并清理运行时（删除会话 / 页面卸载时调用） */
  function disposeRuntime(sid: string): void {
    const rt = runtimes[sid]
    if (!rt) return
    rt.controller?.abort()
    delete runtimes[sid]
  }

  function disposeAllRuntimes(): void {
    Object.keys(runtimes).forEach(disposeRuntime)
  }

  const generatingSessionIds = computed(() =>
    Object.keys(runtimes).filter(sid => runtimes[sid].generating),
  )

  function isSessionGenerating(sid: string): boolean {
    return !!runtimes[sid]?.generating
  }

  return {
    runtimes,
    getRuntime,
    ensureRuntime,
    isActiveCallback,
    markGenerating,
    finishGenerating,
    markUnread,
    markRead,
    disposeRuntime,
    disposeAllRuntimes,
    generatingSessionIds,
    isSessionGenerating,
  }
}
