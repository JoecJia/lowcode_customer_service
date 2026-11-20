<script setup lang="ts">
import { ref } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import type { ContextChange } from '../composables/useMaintenanceChat'

const props = defineProps<{
  batchNo: string
  itemCount: number
  changes: ContextChange[]
}>()
const emit = defineEmits<{
  confirmed: [batchNo: string, action: 'apply' | 'discard', ok: boolean, status?: number]
}>()
const busy = ref(false)

async function confirm(action: 'apply' | 'discard') {
  const targets = props.changes.map(c => c.target).join('\n')
  try {
    await ElMessageBox.confirm(
      `${action === 'apply' ? '确认并入' : '取消'}该批次的 ${props.itemCount} 项变更？\n目标文件：\n${targets}`,
      '确认操作', { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' },
    )
  } catch { return }
  busy.value = true
  try {
    emit('confirmed', props.batchNo, action, true)
  } finally { busy.value = false }
}

function onConfirmResult(ok: boolean, status?: number) {
  busy.value = false
  if (!ok && status === 409) {
    ElMessage.error('文件已被修改，批次已作废，请基于最新版本重新生成')
  }
}

defineExpose({ onConfirmResult })
</script>

<template>
  <div class="batch-bar">
    <span class="batch-label">🟡 本批次共 {{ itemCount }} 项变更 · #{{ batchNo.slice(-6) }}</span>
    <div class="batch-actions">
      <button class="btn-apply" :disabled="busy" @click="confirm('apply')">确认并入（{{ itemCount }} 项）</button>
      <button class="btn-discard" :disabled="busy" @click="confirm('discard')">取消</button>
    </div>
  </div>
</template>

<style scoped>
.batch-bar { border: 1px dashed var(--color-warning); border-radius: var(--radius-sm); background: rgba(251,162,51,.06); padding: 8px 10px; margin: 8px 0; display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.batch-label { font-size: 12px; color: var(--color-text-secondary); }
.batch-actions { display: flex; gap: 8px; }
.btn-apply { border: none; background: var(--color-primary); color: #fff; border-radius: var(--radius-sm); padding: 5px 12px; cursor: pointer; font-size: 12px; }
.btn-apply:disabled, .btn-discard:disabled { opacity: .5; cursor: not-allowed; }
.btn-discard { border: 1px solid var(--color-border); background: var(--color-bg-card); border-radius: var(--radius-sm); padding: 5px 12px; cursor: pointer; font-size: 12px; }
</style>
