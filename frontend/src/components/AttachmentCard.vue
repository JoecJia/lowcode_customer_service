<script setup lang="ts">
import { computed } from 'vue'
import type { ChatAttachment, PendingAttachment } from '../api/chat'

const props = withDefaults(defineProps<{
  attachment: ChatAttachment | PendingAttachment
  removable?: boolean
  clickable?: boolean
}>(), {
  removable: false,
  clickable: false,
})

const emit = defineEmits<{
  remove: []
  open: []
}>()

const isPdf = computed(() => props.attachment.kind === 'pdf')
const hasError = computed(() => 'status' in props.attachment && props.attachment.status === 'error')
const meta = computed(() => {
  const a = props.attachment
  return `${isPdf.value ? 'PDF' : a.mime.split('/')[1].toUpperCase()} · ${formatSize(a.size)}`
})

function formatSize(size: number): string {
  if (!Number.isFinite(size)) return ''
  if (size < 1024) return `${size}B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)}KB`
  return `${(size / 1024 / 1024).toFixed(2)}MB`
}
</script>

<template>
  <div
    class="attachment-card"
    :class="{ pdf: isPdf, error: hasError, clickable: clickable }"
    :title="attachment.name"
    @click="clickable && emit('open')"
  >
    <span class="att-icon">{{ isPdf ? 'PDF' : 'IMG' }}</span>
    <span class="att-info">
      <span class="att-name">{{ attachment.name }}</span>
      <span class="att-meta">{{ hasError ? '处理失败' : meta }}</span>
    </span>
    <button
      v-if="removable"
      class="att-remove"
      type="button"
      title="移除附件"
      @click.stop="emit('remove')"
    >
      <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M3 3l6 6M9 3l-6 6" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.attachment-card {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  min-width: 0;
  max-width: 230px;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg-hover);
  color: var(--color-text-secondary);
  transition: border-color .2s ease, background .2s ease;
}

.attachment-card.pdf {
  border-color: rgba(245, 63, 63, .25);
}

.attachment-card.error {
  border-color: var(--color-danger);
  background: rgba(245, 63, 63, .06);
}

.attachment-card.clickable {
  cursor: pointer;
}

.attachment-card.clickable:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}

.att-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  background: #E8F7F5;
  color: #12A594;
  font-size: 10px;
  font-weight: 700;
}

.attachment-card.pdf .att-icon {
  background: rgba(245, 63, 63, .10);
  color: var(--color-danger);
}

.att-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}

.att-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 150px;
  font-size: 12px;
  color: var(--color-text-primary);
}

.att-meta {
  margin-top: 2px;
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.att-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
}

.att-remove:hover {
  background: var(--color-border-light);
  color: var(--color-text-primary);
}

.att-remove svg {
  width: 10px;
  height: 10px;
}
</style>
