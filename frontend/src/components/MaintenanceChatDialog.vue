<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useMaintenanceChat, type ChatTab } from '../composables/useMaintenanceChat'
import type { UIMessage } from '../components/messageUtils'
import { renderMarkdown, formatTime, showTimeDivider, cleanReasoning } from '../components/messageUtils'
import MaintenanceHistoryModal from './MaintenanceHistoryModal.vue'
import ContextChangeCard from './ContextChangeCard.vue'
import ContextBatchConfirmBar from './ContextBatchConfirmBar.vue'
import type { AdminSession } from '../api/admin'

const emit = defineEmits<{ collapse: [] }>()
const chat = useMaintenanceChat()
const { tabs, activeTabId, activeTab } = chat
const historyVisible = ref(false)
const draft = ref('')
const messageArea = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const TEXTAREA_MAX = 120

onMounted(async () => {
  // 优先恢复上次未关闭的会话，没有可恢复的才新建（避免每打开一次就多一个空会话）
  if (!chat.tabs.value.length && !(await chat.restoreTabs())) await chat.createTab()
  nextTick(autoResizeTextarea)
  scrollBottom()
})

function scrollBottom() { nextTick(() => { if (messageArea.value) messageArea.value.scrollTop = messageArea.value.scrollHeight }) }

function autoResizeTextarea() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, TEXTAREA_MAX) + 'px'
  el.style.overflowY = el.scrollHeight > TEXTAREA_MAX ? 'auto' : 'hidden'
}
watch(draft, () => nextTick(autoResizeTextarea))

function send() {
  const text = draft.value.trim()
  const tab = activeTab.value
  if (!text || !tab || tab.streaming) return
  draft.value = ''
  nextTick(autoResizeTextarea)
  chat.send(tab, text)
  scrollBottom()
}
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send() }
}
function onHistoryOpen(s: AdminSession) {
  chat.openTab(s.id, s.title || '新对话')
  scrollBottom()
}
function onHistoryRenamed(id: string, title: string) {
  const tab = chat.tabs.value.find(t => t.sessionId === id)
  if (tab) { tab.title = title; tab.titleStatus = 'ready' }
}

async function onBatchConfirmed(
  tab: ChatTab, batchId: number | undefined, batchNo: string, action: 'apply' | 'discard',
) {
  const resp = await chat.confirmBatch(tab, batchId, batchNo, action)
  if (resp.ok) {
    ElMessage.success(action === 'apply' ? '已并入知识库' : '已取消该批次')
  } else {
    const status = resp.status
    if (status === 409) ElMessage.error('文件已被修改，批次已作废，请基于最新版本重新生成')
    else if (status === 0) ElMessage.error('批次信息缺失，请重新打开助手后重试')
    else ElMessage.error('操作失败')
  }
}

function visibleSteps(msg: UIMessage) { return msg.steps || [] }
function avatarText(msg: UIMessage) { return msg.role === 'assistant' ? 'AI' : '管' }
</script>

<template>
  <div class="dialog">
    <!-- 工具栏：历史记录 / 新建对话 / 收起 统一 Icon -->
    <div class="toolbar">
      <div class="toolbar-brand">
        <img class="brand-icon" src="/ai-assistant.svg" alt="" />
        <span>维护助手</span>
      </div>
      <div class="toolbar-actions">
        <button class="icon-btn" title="历史记录" @click="historyVisible = true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/></svg>
        </button>
        <button class="icon-btn" title="新建对话" @click="chat.createTab()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <button class="icon-btn" title="收起" @click="emit('collapse')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
      </div>
    </div>

    <div class="tab-strip">
      <div v-for="tab in tabs" :key="tab.id" class="tab-item" :class="{ active: tab.id === activeTabId }" @click="chat.activate(tab.id)">
        <span>{{ tab.titleStatus === 'pending' ? '新对话' : tab.title }}</span>
        <span v-if="tab.streaming" class="tab-loading"></span>
        <button class="tab-close" title="关闭对话" @click.stop="chat.closeTab(tab)">×</button>
      </div>
    </div>

    <div ref="messageArea" class="message-area">
      <template v-if="activeTab">
        <template v-for="(msg, i) in activeTab.messages" :key="msg.id || i">
          <div v-if="showTimeDivider(activeTab.messages[i - 1], msg)" class="time-divider">{{ formatTime(msg.created_at) }}</div>
          <div class="msg-group" :class="msg.role">
            <div class="msg-avatar">
              <img
                v-if="msg.role === 'assistant'"
                src="/ai-assistant.svg"
                alt="assistant"
                class="avatar-img"
              />
              <span v-else>{{ avatarText(msg) }}</span>
            </div>
            <div class="msg-body">
              <div class="msg-bubble">
                <!-- 思考过程：与前台对话一致 -->
                <div
                  v-if="msg.role === 'assistant' && (msg.reasoning || msg.isStreaming || (msg.steps && msg.steps.length > 0))"
                  class="thinking-block"
                  :class="{ collapsed: !msg.showThinking }"
                >
                  <div class="thinking-header" @click="msg.showThinking = !msg.showThinking">
                    <svg class="thinking-clock-icon" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                      <circle cx="7" cy="7" r="5.5"/><path d="M7 4v3.5L9 9"/>
                    </svg>
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
                      <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 5l3 3 3-3"/></svg>
                    </span>
                  </div>
                  <div class="thinking-steps">
                    <template v-for="(st, si) in visibleSteps(msg)" :key="si">
                      <div v-if="st.kind === 'reasoning'" class="reasoning-text">{{ st.clean ?? cleanReasoning(st.text || '') }}</div>
                      <div v-else-if="st.task?.type === 'knowledge_retrieval'" class="retrieval-card">
                        <div class="retrieval-header">
                          <svg class="retrieval-icon" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                            <circle cx="6" cy="6" r="4"/><path d="M9 9l3.5 3.5"/>
                          </svg>
                          <span class="retrieval-title">知识库检索结果</span>
                          <span v-if="st.task?.query" class="retrieval-query" :title="st.task?.query">{{ st.task?.query }}</span>
                        </div>
                        <div class="retrieval-text">{{ st.task?.hitText || st.task?.result }}</div>
                        <div v-if="st.task?.images && st.task.images.length > 0" class="retrieval-images">
                          <div
                            v-for="(img, ii) in st.task.images"
                            :key="ii"
                            class="retrieval-image"
                            :title="img.source || img.alt"
                          >
                            <img :src="img.path" :alt="img.alt" />
                            <span class="retrieval-image-alt">{{ img.alt }}</span>
                          </div>
                        </div>
                      </div>
                      <div v-else-if="st.task" class="task-item">
                        <span class="task-badge">{{ st.task.type }}</span>
                        <span class="task-result">{{ st.task.result }}</span>
                      </div>
                    </template>
                    <div v-if="msg.isStreaming && (!msg.steps || msg.steps.length === 0)" class="thinking-placeholder">正在分析...</div>
                  </div>
                </div>
                <div
                  v-if="msg.role === 'assistant' && (msg.reasoning || (msg.steps && msg.steps.length > 0)) && msg.content"
                  class="thinking-divider"
                ></div>
                <div v-if="msg.content" class="msg-content" v-html="msg._renderedHtml ?? renderMarkdown(msg.content)"></div>
                <div v-if="msg.error" class="msg-error">{{ msg.error }}</div>
              </div>
            </div>
          </div>
        </template>

        <!-- 变更卡片 + 批次确认条：整个会话只渲染一份，避免随助手消息条数重复 -->
        <div v-for="group in chat.getBatchGroups(activeTab)" :key="group.batch_no" class="change-group">
          <ContextChangeCard v-for="ch in group.changes" :key="ch.batch_no + '-' + ch.item_index" :item="ch" />
          <ContextBatchConfirmBar
            v-if="group.changes.some(c => c.op !== 'applied')"
            :batch-id="group.batch_id"
            :batch-no="group.batch_no"
            :item-count="group.item_count"
            :changes="group.changes"
            @confirmed="(id, bn, action) => onBatchConfirmed(activeTab!, id, bn, action)"
          />
          <div v-else class="batch-done">✅ 已并入（批次 #{{ group.batch_no.slice(-6) }}）</div>
        </div>
      </template>
    </div>

    <div class="composer">
      <textarea
        ref="textareaRef"
        v-model="draft"
        placeholder="输入维护诉求，Enter 发送 / Shift+Enter 换行"
        :disabled="activeTab?.streaming"
        rows="1"
        @keydown="handleKeydown"
      ></textarea>
      <button class="send" title="发送" :disabled="!draft.trim() || activeTab?.streaming" @click="send">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
      </button>
    </div>
    <MaintenanceHistoryModal v-model:visible="historyVisible" @open="onHistoryOpen" @renamed="onHistoryRenamed" />
  </div>
</template>

<style scoped>
.dialog { display: flex; flex-direction: column; width: 100%; height: 100%; background: var(--color-bg-card); }

/* 工具栏 */
.toolbar { height: 52px; flex: none; display: flex; align-items: center; justify-content: space-between; padding: 0 var(--spacing-lg); border-bottom: 1px solid var(--color-border-light); }
.toolbar-brand { display: flex; align-items: center; gap: var(--spacing-sm); font-size: 15px; font-weight: 600; }
.toolbar-brand .brand-icon { width: 20px; height: 20px; object-fit: contain; }
.toolbar-actions { display: flex; gap: var(--spacing-xs); }
.icon-btn { width: 32px; height: 32px; border: none; border-radius: var(--radius-sm); background: transparent; color: var(--color-text-tertiary); display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all .2s ease; }
.icon-btn:hover { background: var(--color-bg-hover); color: var(--color-primary); }
.icon-btn svg { width: 18px; height: 18px; }

/* Tab 栏 */
.tab-strip { display: flex; gap: var(--spacing-xs); padding: 0 var(--spacing-sm); height: 40px; align-items: center; border-bottom: 1px solid var(--color-border-light); overflow-x: auto; flex: none; }
.tab-item { display: flex; align-items: center; gap: var(--spacing-xs); padding: var(--spacing-xs) var(--spacing-sm); border-radius: var(--radius-sm); font-size: 12px; color: var(--color-text-secondary); cursor: pointer; white-space: nowrap; }
.tab-item.active { background: var(--color-primary-light); color: var(--color-primary); }
.tab-loading { width: 6px; height: 6px; border-radius: 50%; background: var(--color-success); }
.tab-close { border: none; background: transparent; color: var(--color-text-disabled); cursor: pointer; font-size: 13px; padding: 0 0 0 2px; line-height: 1; }
.tab-close:hover { color: var(--color-danger); }

/* 消息区：底色与前台一致 */
.message-area { flex: 1; overflow-y: auto; padding: 24px; background: var(--color-bg-page); }
.message-area::-webkit-scrollbar { width: 5px; }
.message-area::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 3px; }
.time-divider { text-align: center; font-size: 12px; color: var(--color-text-tertiary); padding: 16px 0 12px; }

/* 消息组：消息体占满可用宽度，随弹窗宽度自适应 */
.msg-group { display: flex; gap: 10px; margin-bottom: 16px; align-items: flex-start; }
.msg-group.assistant { flex-direction: row; }
.msg-group.user { flex-direction: row-reverse; }
.msg-body { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.msg-group.user .msg-body { align-items: flex-end; }

/* 头像 */
.msg-avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 13px; font-weight: 500; margin-top: 18px; }
.msg-group.assistant .msg-avatar { color: #fff; }
.msg-group.user .msg-avatar { background: linear-gradient(135deg, #a8c0ff, #3f2b96); color: #fff; }
.avatar-img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }

/* 气泡 */
.msg-bubble { padding: 10px 14px; border-radius: var(--radius-md); font-size: 14px; line-height: 22px; word-break: break-word; position: relative; box-shadow: var(--shadow-sm); max-width: 100%; }
.msg-group.assistant .msg-bubble { background: var(--color-bg-card); color: var(--color-text-primary); border-top-left-radius: 4px; border: 1px solid var(--color-border-light); }
.msg-group.user .msg-bubble { background: var(--color-primary); color: #FFFFFF; border-top-right-radius: 4px; box-shadow: 0 2px 8px rgba(43,103,255,0.25); }

/* 思考过程（与前台一致） */
.thinking-block { border: 1px solid var(--color-border-light); border-radius: var(--radius-sm); margin-bottom: 12px; overflow: hidden; background: #FAFBFC; }
.thinking-header { display: flex; align-items: center; gap: 6px; padding: 8px 12px; font-size: 12px; color: var(--color-text-tertiary); cursor: pointer; user-select: none; transition: background 0.15s ease; }
.thinking-header:hover { background: var(--color-bg-hover); }
.thinking-header svg { width: 14px; height: 14px; }
.thinking-toggle { margin-left: auto; transition: transform 0.2s ease; color: var(--color-text-tertiary); flex-shrink: 0; }
.thinking-toggle svg { width: 12px; height: 12px; }
.thinking-block.collapsed .thinking-toggle { transform: rotate(-90deg); }
.thinking-clock-icon { flex-shrink: 0; }
.thinking-label { font-size: 12px; }
.thinking-label.thinking-active { color: var(--color-primary); font-weight: 500; }
.thinking-dots { display: inline-flex; align-items: center; gap: 3px; margin-left: 4px; vertical-align: middle; }
.thinking-dot { display: inline-block; width: 5px; height: 5px; border-radius: 50%; background: var(--color-primary); animation: thinkingPulse 1.2s ease-in-out infinite; }
.thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes thinkingPulse { 0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); } 30% { opacity: 1; transform: scale(1); } }
.thinking-steps { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; font-size: 12px; color: var(--color-text-tertiary); line-height: 20px; max-height: 300px; overflow-y: auto; border-top: 1px solid var(--color-border-light); }
.thinking-block.collapsed .thinking-steps { display: none; }
.thinking-steps::-webkit-scrollbar { width: 3px; }
.thinking-steps::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 2px; }
.task-item { padding: 6px 8px; background: #F0F4FF; border-radius: var(--radius-sm); border-left: 3px solid var(--color-primary); }
.task-badge { display: inline-block; font-size: 11px; font-weight: 600; color: var(--color-primary); background: #E0E8FF; padding: 1px 6px; border-radius: 3px; margin-right: 6px; }
.task-result { display: block; margin-top: 4px; max-height: 160px; overflow-y: auto; white-space: pre-wrap; color: var(--color-text-secondary); word-break: break-word; }
.reasoning-text { white-space: pre-wrap; word-break: break-word; }
.thinking-placeholder { color: var(--color-text-disabled); font-style: italic; }
.retrieval-card { border: 1px solid #E0E8FF; border-left: 3px solid var(--color-primary); border-radius: var(--radius-sm); background: #F7F9FF; padding: 8px 10px; }
.retrieval-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; min-width: 0; }
.retrieval-icon { width: 13px; height: 13px; flex: none; color: var(--color-primary); }
.retrieval-title { flex: none; font-size: 12px; font-weight: 600; color: var(--color-primary); }
.retrieval-query { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; color: var(--color-text-tertiary); background: #E0E8FF; border-radius: 3px; padding: 1px 6px; }
.retrieval-text { max-height: 220px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 19px; color: var(--color-text-secondary); }
.retrieval-images { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.retrieval-image { width: 96px; cursor: zoom-in; display: flex; flex-direction: column; gap: 3px; }
.retrieval-image img { width: 96px; height: 72px; object-fit: cover; border: 1px solid var(--color-border-light); border-radius: var(--radius-sm); background: #fff; }
.retrieval-image-alt { font-size: 11px; color: var(--color-text-tertiary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.thinking-divider { height: 1px; background: var(--color-border-light); margin: 12px 0; }

/* 正文 markdown（与前台一致） */
.msg-content :deep(p) { margin-bottom: 6px; }
.msg-content :deep(p:last-child) { margin-bottom: 0; }
.msg-content :deep(img) { max-width: 100%; height: auto; border-radius: var(--radius-sm); }
.msg-content :deep(strong) { font-weight: 600; }
.msg-content :deep(code) { background: rgba(0,0,0,0.06); padding: 2px 5px; border-radius: 3px; font-size: 13px; }
.msg-content :deep(pre) { background: #f5f6fa; padding: 10px 14px; border-radius: var(--radius-sm); overflow-x: auto; margin: 8px 0; }
.msg-content :deep(pre code) { background: transparent; padding: 0; }
.msg-content :deep(ul), .msg-content :deep(ol) { padding-left: 20px; margin: 4px 0; }
.msg-content :deep(blockquote) { border-left: 3px solid var(--color-primary); padding-left: 10px; color: var(--color-text-secondary); margin: 6px 0; }
.msg-error { margin-top: 8px; padding: 8px 12px; font-size: 12px; color: #ef4444; background: #fef2f2; border: 1px solid #fecaca; border-radius: var(--radius-sm); line-height: 1.5; word-break: break-all; max-height: 120px; overflow-y: auto; }
.change-group { margin: 12px 0 16px 46px; }
.batch-done { font-size: 12px; color: var(--color-success); padding: 6px 0; }

/* 输入区 */
.composer { flex: none; padding: var(--spacing-md) var(--spacing-lg) var(--spacing-sm); border-top: 1px solid var(--color-border-light); display: flex; gap: var(--spacing-sm); align-items: flex-end; }
.composer textarea { flex: 1; min-height: 36px; max-height: 120px; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: 14px; font-family: inherit; line-height: 20px; outline: none; resize: none; overflow-y: hidden; transition: border-color .2s; }
.composer textarea:focus { border-color: var(--color-primary); }
.composer textarea:disabled { background: var(--color-bg-hover); }
.composer .send { width: 36px; height: 36px; flex: none; border: none; border-radius: var(--radius-sm); background: var(--color-primary); color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background .2s; }
.composer .send:hover { background: var(--color-primary-hover); }
.composer .send:disabled { opacity: .5; cursor: not-allowed; }
.composer .send svg { width: 18px; height: 18px; }
</style>
