<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import type { AttachmentPayload } from '../api/chat'
import { useAttachments } from '../composables/useAttachments'
import AttachmentCard from './AttachmentCard.vue'

const props = defineProps<{
  streaming: boolean
  /** 文本草稿由父组件按会话保存；附件仍由组件内部管理 */
  modelValue?: string
}>()

const emit = defineEmits<{
  send: [payload: { text: string; attachments: AttachmentPayload[] }]
  stop: []
  'update:modelValue': [value: string]
}>()

const { attachments, addFiles, remove, reset, getPayloads } = useAttachments()
const text = computed({
  get: () => props.modelValue ?? '',
  set: (v: string) => emit('update:modelValue', v),
})
const fileInput = ref<HTMLInputElement>()
const textarea = ref<HTMLTextAreaElement>()
const isDragOver = ref(false)
const isComposing = ref(false)

const canSend = computed(() => !!text.value.trim() || attachments.value.length > 0)

function autoResize() {
  const el = textarea.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 150) + 'px'
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !isComposing.value) {
    e.preventDefault()
    handleSend()
  }
}

async function handleSend() {
  if (!canSend.value) return
  const payloads = await getPayloads()
  emit('send', { text: text.value.trim(), attachments: payloads })
  emit('update:modelValue', '')
  reset()
  await nextTick()
  autoResize()
}

function openFilePicker() {
  fileInput.value?.click()
}

async function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  await addFiles(files)
  input.value = ''
}

function extractFiles(items?: DataTransferItemList | null): File[] {
  if (!items) return []
  const files: File[] = []
  for (const item of Array.from(items)) {
    if (item.kind !== 'file') continue
    const file = item.getAsFile()
    if (file) files.push(file)
  }
  return files
}

async function handlePaste(e: ClipboardEvent) {
  const files = extractFiles(e.clipboardData?.items)
  const valid = files.filter(f =>
    f.type.startsWith('image/') || f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'),
  )
  if (!valid.length) return
  e.preventDefault()
  await addFiles(valid)
}

function handleDragOver(e: DragEvent) {
  e.preventDefault()
  isDragOver.value = true
}

function handleDragLeave(e: DragEvent) {
  if (e.currentTarget === e.target) return
  isDragOver.value = false
}

async function handleDrop(e: DragEvent) {
  e.preventDefault()
  isDragOver.value = false
  await addFiles(Array.from(e.dataTransfer?.files || []))
}
</script>

<template>
  <div
    class="chat-input-card"
    :class="{ 'drag-over': isDragOver }"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
  >
    <div v-if="attachments.length" class="attachment-list">
      <AttachmentCard
        v-for="att in attachments"
        :key="att.id"
        :attachment="att"
        removable
        @remove="remove(att.id)"
      />
    </div>

    <textarea
      ref="textarea"
      v-model="text"
      class="msg-input"
      placeholder="请将文本粘贴到此处..."
      rows="1"
      :disabled="streaming"
      @keydown="handleKeydown"
      @compositionstart="isComposing = true"
      @compositionend="isComposing = false"
      @input="autoResize"
      @paste="handlePaste"
    ></textarea>

    <div class="input-footer">
      <div class="footer-left">
        <button class="btn-attach" type="button" title="上传图片或 PDF" @click="openFilePicker">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M5.5 7.5l4-4a2.5 2.5 0 013.5 3.5l-5.5 5.5a4 4 0 01-5.5-5.5l5-5" />
          </svg>
        </button>
        <span class="attach-status">
          {{ attachments.length ? `已上传 ${attachments.length} 个文件` : '支持粘贴、拖拽或点击上传图片/PDF' }}
        </span>
        <input
          ref="fileInput"
          class="file-input"
          type="file"
          multiple
          accept="image/png,image/jpeg,image/webp,application/pdf,.pdf"
          @change="onFileChange"
        />
      </div>

      <button
        class="btn-send"
        :class="{ stop: streaming }"
        :disabled="!streaming && !canSend"
        type="button"
        :title="streaming ? '停止生成' : '发送'"
        @click="streaming ? emit('stop') : handleSend()"
      >
        <svg v-if="!streaming" viewBox="0 0 18 18" fill="currentColor">
          <path d="M1.5 2.5l15 6.5-15 6.5 3-6.5-3-6.5z" />
        </svg>
        <svg v-else viewBox="0 0 16 16" fill="currentColor">
          <rect x="3" y="3" width="10" height="10" rx="1" />
        </svg>
        <span>{{ streaming ? '停止' : '发送' }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-input-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-card);
  padding: var(--spacing-md);
  transition: border-color .2s ease, box-shadow .2s ease, background .2s ease;
}

.chat-input-card:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(43, 103, 255, .10);
}

.chat-input-card.drag-over {
  border-style: dashed;
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}

.attachment-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.msg-input {
  display: block;
  width: 100%;
  min-height: 64px;
  max-height: 150px;
  padding: 0;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--color-text-primary);
  font-family: inherit;
  font-size: 14px;
  line-height: 22px;
}

.msg-input:disabled {
  color: var(--color-text-disabled);
  cursor: not-allowed;
}

.msg-input::placeholder {
  color: var(--color-text-disabled);
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--spacing-sm);
}

.footer-left {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  min-width: 0;
}

.btn-attach {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
}

.btn-attach:hover {
  background: var(--color-bg-hover);
  color: var(--color-primary);
}

.btn-attach svg {
  width: 16px;
  height: 16px;
}

.attach-status {
  font-size: 12px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-input {
  display: none;
}

.btn-send {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 84px;
  height: 32px;
  padding: 0 14px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: background .2s ease;
}

.btn-send:hover {
  background: var(--color-primary-hover);
}

.btn-send:active {
  background: var(--color-primary-active);
}

.btn-send:disabled {
  background: var(--color-text-disabled);
  cursor: not-allowed;
}

.btn-send.stop {
  background: var(--color-danger);
}

.btn-send svg {
  width: 14px;
  height: 14px;
}
</style>
