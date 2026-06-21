<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getFeedbacks, getFeedbackDetail, resolveFeedback } from '../../api/admin'

interface FeedbackItem {
  id: number
  session_id: string
  username: string
  user_id: number
  session_title: string
  status: string
  message_count: number
  last_active: number
  created_at: number
}

interface Message {
  id: number
  role: string
  content: string
  reasoning_content: string
  created_at: number
}

interface QAPair {
  question: string
  answer: string
}

const filterStatus = ref('all')
const feedbacks = ref<FeedbackItem[]>([])
const total = ref(0)
const offset = ref(0)
const limit = 20
const hasMore = ref(false)
const loadingList = ref(false)

const selectedFeedbackId = ref<number | null>(null)
const messages = ref<Message[]>([])
const feedbackDetail = ref<any>(null)
const loadingDetail = ref(false)

const qaPairs = ref<QAPair[]>([{ question: '', answer: '' }])
const resolving = ref(false)

const resizerWidth = ref(320)

// 按日期分组
const dateGroups = computed(() => {
  const groups: { date: string; expanded: boolean; items: FeedbackItem[] }[] = []
  const expandedMap: Record<string, boolean> = {}
  for (const fb of feedbacks.value) {
    const date = new Date(fb.created_at * 1000).toLocaleDateString('zh-CN')
    if (!expandedMap[date]) {
      expandedMap[date] = true
      groups.push({ date, expanded: true, items: [] })
    }
    groups[groups.length - 1].items.push(fb)
  }
  return groups
})

onMounted(() => {
  loadFeedbacks()
})

async function loadFeedbacks(reset = true) {
  if (loadingList.value) return
  loadingList.value = true

  try {
    const params: Record<string, string> = {
      status: filterStatus.value,
      limit: String(limit),
      offset: String(reset ? 0 : offset.value),
    }
    const resp = await getFeedbacks(params)
    const data = await resp.json()
    if (data.ok) {
      if (reset) {
        feedbacks.value = data.data.feedbacks
        offset.value = data.data.feedbacks.length
      } else {
        feedbacks.value = [...feedbacks.value, ...data.data.feedbacks]
        offset.value += data.data.feedbacks.length
      }
      total.value = data.data.total
      hasMore.value = feedbacks.value.length < data.data.total
    }
  } catch {
    ElMessage.error('加载反馈列表失败')
  } finally {
    loadingList.value = false
  }
}

function onFilterChange() {
  selectedFeedbackId.value = null
  messages.value = []
  qaPairs.value = [{ question: '', answer: '' }]
  loadFeedbacks(true)
}

function onListScroll(e: Event) {
  const el = e.target as HTMLElement
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 20 && hasMore.value && !loadingList.value) {
    loadFeedbacks(false)
  }
}

function toggleDateGroup(idx: number) {
  dateGroups.value[idx].expanded = !dateGroups.value[idx].expanded
}

async function selectFeedback(fb: FeedbackItem) {
  selectedFeedbackId.value = fb.id
  loadingDetail.value = true
  messages.value = []

  try {
    const resp = await getFeedbackDetail(fb.id)
    const data = await resp.json()
    if (data.ok) {
      feedbackDetail.value = data.data.feedback
      messages.value = data.data.messages

      // 自动为每条用户消息生成 Q&A 条目
      const userMessages = data.data.messages.filter((m: Message) => m.role === 'user')
      qaPairs.value = userMessages.map((m: Message) => ({
        question: m.content,
        answer: '',
      }))
      if (qaPairs.value.length === 0) {
        qaPairs.value = [{ question: '', answer: '' }]
      }
    }
  } catch {
    ElMessage.error('加载反馈详情失败')
  } finally {
    loadingDetail.value = false
  }
}

function addQAPair() {
  qaPairs.value.push({ question: '', answer: '' })
}

function removeQAPair(idx: number) {
  if (qaPairs.value.length <= 1) return
  qaPairs.value.splice(idx, 1)
}

async function handleResolve() {
  const validPairs = qaPairs.value.filter((qa) => qa.answer.trim())
  if (validPairs.length === 0) {
    ElMessage.warning('请至少填写一条回答')
    return
  }

  if (!selectedFeedbackId.value) return
  resolving.value = true

  try {
    const resp = await resolveFeedback(selectedFeedbackId.value, validPairs)
    const data = await resp.json()
    if (data.ok) {
      ElMessage.success(data.message || '处理成功')
      qaPairs.value = [{ question: '', answer: '' }]
      selectedFeedbackId.value = null
      messages.value = []
      loadFeedbacks(true)
    } else {
      ElMessage.error(data.detail || '处理失败')
    }
  } catch {
    ElMessage.error('处理失败')
  } finally {
    resolving.value = false
  }
}

async function copyMessage(content: string) {
  try {
    await navigator.clipboard.writeText(content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// 拖拽分隔条
let isDragging = false
function onResizerMouseDown(e: MouseEvent) {
  isDragging = true
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
  e.preventDefault()
}

function onMouseMove(e: MouseEvent) {
  if (!isDragging) return
  const container = (e.target as HTMLElement).closest('.tab-feedback')
  if (!container) return
  const rect = container.getBoundingClientRect()
  const newWidth = rect.right - e.clientX
  resizerWidth.value = Math.max(240, Math.min(newWidth, rect.width * 0.5))
}

function onMouseUp() {
  isDragging = false
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
}
</script>

<template>
  <div class="tab-feedback">
    <!-- 左侧反馈列表 -->
    <div class="feedback-list-panel">
      <div class="feedback-filter">
        <el-select v-model="filterStatus" size="small" @change="onFilterChange">
          <el-option label="全部" value="all" />
          <el-option label="待处理" value="pending" />
          <el-option label="已处理" value="resolved" />
        </el-select>
      </div>

      <div class="feedback-list-scroll" @scroll="onListScroll">
        <div v-if="feedbacks.length === 0 && !loadingList" class="list-empty">
          暂无反馈数据
        </div>

        <div v-for="(group, gi) in dateGroups" :key="group.date" class="feedback-date-group">
          <div class="feedback-date-label" @click="toggleDateGroup(gi)">
            <span class="date-arrow">{{ group.expanded ? '▼' : '▶' }}</span>
            📅 {{ group.date }}
            <span class="date-count">{{ group.items.length }}</span>
          </div>

          <div v-if="group.expanded" class="feedback-items">
            <div
              v-for="fb in group.items"
              :key="fb.id"
              class="feedback-item"
              :class="{ active: selectedFeedbackId === fb.id }"
              @click="selectFeedback(fb)"
            >
              <div class="feedback-item-header">
                <span class="feedback-user">{{ fb.username }}</span>
                <el-tag
                  :type="fb.status === 'pending' ? 'warning' : 'info'"
                  size="small"
                >
                  {{ fb.status === 'pending' ? '待处理' : '已处理' }}
                </el-tag>
              </div>
              <div class="feedback-item-subject">{{ fb.session_title || '无标题' }}</div>
              <div class="feedback-item-meta">
                {{ formatTime(fb.created_at) }} · {{ fb.message_count || 0 }}条消息
              </div>
            </div>
          </div>
        </div>

        <div v-if="hasMore" class="load-more" @click="loadFeedbacks(false)">
          加载更多...
        </div>
        <div v-if="loadingList" class="list-loading">加载中...</div>
      </div>
    </div>

    <!-- 右侧详情区 -->
    <div class="feedback-detail-panel" v-if="selectedFeedbackId">
      <!-- 对话区 -->
      <div class="feedback-conversation" :style="{ flex: `1 1 calc(100% - ${resizerWidth}px - 6px)` }">
        <div class="conversation-header" v-if="feedbackDetail">
          <span>{{ feedbackDetail.username }} 的对话</span>
          <el-tag :type="feedbackDetail.status === 'pending' ? 'warning' : 'info'" size="small">
            {{ feedbackDetail.status === 'pending' ? '待处理' : '已处理' }}
          </el-tag>
        </div>
        <div class="conversation-messages" v-loading="loadingDetail">
          <div
            v-for="msg in messages"
            :key="msg.id"
            class="chat-bubble-row"
            :class="{ 'chat-bubble-row--user': msg.role === 'user' }"
          >
            <div class="chat-bubble-avatar">
              {{ msg.role === 'user' ? '👤' : '🤖' }}
            </div>
            <div class="chat-bubble-wrapper">
              <div
                class="chat-bubble"
                :class="{
                  'chat-bubble--user': msg.role === 'user',
                  'chat-bubble--ai': msg.role !== 'user',
                }"
              >
                {{ msg.content }}
              </div>
              <button
                class="chat-msg-copy-btn"
                @click="copyMessage(msg.content)"
                title="复制"
              >
                📋
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 拖拽分隔条 -->
      <div class="feedback-resizer" @mousedown="onResizerMouseDown"></div>

      <!-- 改写区 -->
      <div class="feedback-rewrite-col" :style="{ width: resizerWidth + 'px', minWidth: '240px' }">
        <div class="rewrite-header">改写回答</div>
        <div class="rewrite-body">
          <div v-for="(qa, idx) in qaPairs" :key="idx" class="qa-pair-item">
            <div class="qa-pair-header">
              <span>Q&A #{{ idx + 1 }}</span>
              <button
                v-if="qaPairs.length > 1"
                class="qa-remove-btn"
                @click="removeQAPair(idx)"
              >
                ✕
              </button>
            </div>
            <el-input
              v-model="qa.question"
              type="textarea"
              placeholder="用户原始问题…"
              :rows="1"
              class="qa-input"
            />
            <el-input
              v-model="qa.answer"
              type="textarea"
              placeholder="输入管理员回复…"
              :rows="2"
              class="qa-input"
            />
          </div>

          <el-button class="qa-add-btn" @click="addQAPair">
            ＋ 添加 Q&A
          </el-button>

          <el-button
            type="primary"
            class="qa-resolve-btn"
            :loading="resolving"
            :disabled="!qaPairs.some(q => q.answer.trim())"
            @click="handleResolve"
          >
            完成处理
          </el-button>
        </div>
      </div>
    </div>

    <!-- 未选择反馈时的空状态 -->
    <div v-else class="feedback-detail-panel feedback-empty">
      <div class="empty-text">选择左侧反馈查看详情</div>
    </div>
  </div>
</template>

<style scoped>
.tab-feedback {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* 左侧列表 */
.feedback-list-panel {
  width: 260px;
  min-width: 260px;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border-light);
}

.feedback-filter {
  padding: 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.feedback-list-scroll {
  flex: 1;
  overflow-y: auto;
}

.list-empty {
  text-align: center;
  padding: 40px 16px;
  color: var(--color-text-tertiary);
  font-size: 14px;
}

.feedback-date-group {
  border-bottom: 1px solid var(--color-border-light);
}

.feedback-date-label {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--color-text-secondary);
  background: var(--color-bg-page);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}

.date-arrow {
  font-size: 10px;
}

.date-count {
  margin-left: auto;
  color: var(--color-text-tertiary);
}

.feedback-item {
  padding: 10px 16px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: all 0.15s ease;
}

.feedback-item:hover {
  background: var(--color-bg-hover);
}

.feedback-item.active {
  background: var(--color-primary-light);
  border-left-color: var(--color-primary);
}

.feedback-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.feedback-user {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.feedback-item-subject {
  font-size: 12px;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 2px;
}

.feedback-item-meta {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.load-more, .list-loading {
  text-align: center;
  padding: 12px;
  font-size: 13px;
  color: var(--color-primary);
  cursor: pointer;
}

/* 右侧详情区 */
.feedback-detail-panel {
  flex: 1;
  display: flex;
  overflow: hidden;
  background: var(--color-bg-page);
}

.feedback-empty {
  align-items: center;
  justify-content: center;
}

.empty-text {
  color: var(--color-text-tertiary);
  font-size: 14px;
}

/* 对话区 */
.feedback-conversation {
  display: flex;
  flex-direction: column;
  min-width: 200px;
}

.conversation-header {
  padding: 12px 16px;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 500;
}

.conversation-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.chat-bubble-row {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.chat-bubble-row--user {
  flex-direction: row-reverse;
}

.chat-bubble-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
  border: 1px solid var(--color-border-light);
}

.chat-bubble-wrapper {
  max-width: 70%;
  display: flex;
  align-items: flex-start;
  gap: 4px;
}

.chat-bubble-row--user .chat-bubble-wrapper {
  flex-direction: row-reverse;
}

.chat-bubble {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.chat-bubble--ai {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  color: var(--color-text-primary);
  border-top-left-radius: 4px;
}

.chat-bubble--user {
  background: var(--color-primary);
  color: #fff;
  border-top-right-radius: 4px;
}

.chat-msg-copy-btn {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-card);
  font-size: 11px;
  padding: 2px 4px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
}

.chat-bubble-row:hover .chat-msg-copy-btn {
  opacity: 1;
}

/* 拖拽分隔条 */
.feedback-resizer {
  width: 6px;
  background: var(--color-border);
  cursor: col-resize;
  flex-shrink: 0;
  transition: background 0.15s;
}

.feedback-resizer:hover {
  background: var(--color-primary);
}

/* 改写区 */
.feedback-rewrite-col {
  background: var(--color-bg-card);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.rewrite-header {
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 500;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.rewrite-body {
  padding: 12px;
  flex: 1;
  overflow-y: auto;
}

.qa-pair-item {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  margin-bottom: 10px;
}

.qa-pair-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}

.qa-remove-btn {
  background: none;
  border: none;
  font-size: 14px;
  color: var(--color-text-tertiary);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.qa-remove-btn:hover {
  color: var(--color-danger);
  background: #FFF0F0;
}

.qa-input {
  margin-bottom: 6px;
}

.qa-add-btn {
  width: auto;
  display: block;
  margin: 0 auto 8px;
  border: 1px dashed var(--color-border);
  color: var(--color-primary);
  background: transparent;
}

.qa-add-btn:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}

.qa-resolve-btn {
  width: auto;
  display: block;
  margin: 0 auto;
}
</style>
