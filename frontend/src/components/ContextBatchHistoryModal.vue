<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getContextBatches, rollbackContextBatch, type ContextBatch,
} from '../api/admin'

defineProps<{ agentName: string }>()
const visible = defineModel<boolean>('visible', { default: false })
const batches = ref<ContextBatch[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const resp = await getContextBatches('applied,rolled_back', 100)
    const data = await resp.json()
    batches.value = data.ok ? (data.data?.batches || []) : []
  } catch { ElMessage.error('加载变更记录失败') }
  finally { loading.value = false }
}
function open() { visible.value = true; load() }
defineExpose({ open })

async function rollback(batch: ContextBatch) {
  try {
    await ElMessageBox.confirm(
      `确定回滚批次 #${batch.batch_no.slice(-6)}（${batch.item_count} 项）吗？将还原到确认前状态。`,
      '一键回滚', { type: 'warning' },
    )
  } catch { return }
  const resp = await rollbackContextBatch(batch.id)
  if (resp.ok) { ElMessage.success('已回滚并更新索引'); load() }
  else ElMessage.error('回滚失败')
}
function statusLabel(s: string) {
  return s === 'applied' ? '已生效' : s === 'rolled_back' ? '已回滚' : s
}
</script>

<template>
  <el-dialog v-model="visible" :title="`${agentName} · 变更记录`" width="720px" append-to-body @open="load">
    <div v-loading="loading" class="batch-list">
      <div v-for="b in batches" :key="b.id" class="batch-item">
        <div class="batch-head">
          <span class="batch-no">#{{ b.batch_no.slice(-6) }}</span>
          <span class="batch-status" :class="b.status">{{ statusLabel(b.status) }}</span>
          <span class="batch-meta">{{ b.item_count }} 项 · {{ b.operator }} · {{ new Date(b.created_at * 1000).toLocaleString() }}</span>
          <el-button v-if="b.status === 'applied'" size="small" type="warning" @click="rollback(b)">一键回滚</el-button>
        </div>
        <div class="batch-summary">{{ b.summary }}</div>
        <div class="batch-files">
          <span v-for="(it, i) in b.items" :key="i" class="file-tag">{{ it.target }}</span>
        </div>
      </div>
      <div v-if="!batches.length && !loading" class="empty">暂无已生效的变更记录</div>
    </div>
    <template #footer>
      <el-button @click="load">刷新</el-button>
      <el-button type="primary" @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.batch-list { max-height: 500px; overflow-y: auto; }
.batch-item { border: 1px solid var(--color-border-light); border-radius: var(--radius-sm); padding: 10px 12px; margin-bottom: 8px; }
.batch-head { display: flex; align-items: center; gap: 8px; }
.batch-no { font-family: monospace; font-weight: 600; }
.batch-status { font-size: 11px; padding: 2px 6px; border-radius: 10px; }
.batch-status.applied { background: rgba(26,127,55,.12); color: #1a7f37; }
.batch-status.rolled_back { background: rgba(100,100,100,.12); color: #888; }
.batch-meta { flex: 1; font-size: 11px; color: var(--color-text-tertiary); }
.batch-summary { font-size: 12px; color: var(--color-text-secondary); margin: 6px 0; }
.batch-files { display: flex; flex-wrap: wrap; gap: 4px; }
.file-tag { font-family: monospace; font-size: 11px; background: var(--color-bg-hover); padding: 2px 6px; border-radius: var(--radius-sm); }
.empty { text-align: center; color: var(--color-text-tertiary); padding: 32px 0; font-size: 13px; }
</style>
