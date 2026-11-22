<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { listAdminSessions, renameAdminSession } from '../api/admin'
import type { AdminSession } from '../api/admin'

const visible = defineModel<boolean>('visible', { default: false })
const emit = defineEmits<{ open: [session: AdminSession]; renamed: [id: string, title: string] }>()
const sessions = ref<AdminSession[]>([])
const keyword = ref('')
const loading = ref(false)
const editingId = ref('')
const renameValue = ref('')
const renameInputRef = ref<HTMLInputElement | null>(null)

function notify(message: string, type: 'success' | 'warning' | 'error' | 'info' = 'info') {
  ElMessage({ message, type, zIndex: 3000 })
}

async function load() {
  loading.value = true
  try { sessions.value = (await listAdminSessions(50, 0)).data?.sessions || [] }
  catch { notify('加载历史失败', 'error') }
  finally { loading.value = false }
}
function open() { visible.value = true; load() }
defineExpose({ open })

function pick(s: AdminSession) {
  if (editingId.value === s.id) return
  emit('open', s); visible.value = false
}
function startRename(s: AdminSession) {
  editingId.value = s.id
  renameValue.value = s.title || '新对话'
  nextTick(() => { renameInputRef.value?.focus(); renameInputRef.value?.select() })
}
function cancelRename() { editingId.value = ''; renameValue.value = '' }
async function saveRename(s: AdminSession) {
  const title = renameValue.value.trim()
  if (!title || title.length > 50) { notify('名称需 1–50 字', 'warning'); return }
  const resp = await renameAdminSession(s.id, title)
  if (resp.ok) {
    s.title = title
    emit('renamed', s.id, title)
    cancelRename()
    notify('已改名', 'success')
  } else notify('改名失败', 'error')
}
function onRenameKeydown(e: KeyboardEvent, s: AdminSession) {
  if (e.key === 'Enter') { e.preventDefault(); saveRename(s) }
  else if (e.key === 'Escape') { e.preventDefault(); cancelRename() }
}
</script>

<template>
  <el-dialog v-model="visible" title="历史对话" width="560px" append-to-body :z-index="2600" @open="load">
    <el-input v-model="keyword" placeholder="搜索会话名称…" clearable style="margin-bottom: 12px" />
    <div v-loading="loading" class="history-list">
      <div v-for="s in sessions.filter(x => !keyword || (x.title || '').includes(keyword))" :key="s.id" class="history-item" :class="{ editing: editingId === s.id }" @click="pick(s)">
        <template v-if="editingId === s.id">
          <div class="rename-inline" @click.stop>
            <input
              ref="renameInputRef"
              v-model="renameValue"
              class="rename-input"
              maxlength="50"
              placeholder="请输入会话名称"
              @keydown="onRenameKeydown($event, s)"
            />
            <button class="rename-confirm" title="确认修改" @click="saveRename(s)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </button>
            <button class="rename-cancel" title="取消" @click="cancelRename">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </template>
        <template v-else>
          <span class="history-title">{{ s.title || '新对话' }}</span>
          <button class="rename-btn" title="重命名" @click.stop="startRename(s)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <div class="history-meta">{{ new Date(s.updated_at * 1000).toLocaleString() }}</div>
        </template>
      </div>
      <div v-if="!sessions.length && !loading" class="history-empty">暂无历史对话</div>
    </div>
    <template #footer>
      <el-button @click="load">刷新</el-button>
      <el-button type="primary" @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.history-list { max-height: 420px; overflow-y: auto; }
.history-item { position: relative; padding: 10px 12px; border-bottom: 1px solid var(--color-border-light); cursor: pointer; }
.history-item:hover { background: var(--color-bg-hover); }
.history-title { font-size: 13px; font-weight: 500; }
.rename-btn { position: absolute; right: 10px; top: 10px; width: 26px; height: 26px; border: none; border-radius: var(--radius-sm); background: transparent; color: var(--color-text-tertiary); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all .2s ease; }
.rename-btn svg { width: 16px; height: 16px; }
.rename-btn:hover { background: var(--color-primary-light); color: var(--color-primary); }

/* 原位编辑 */
.history-item.editing { cursor: default; }
.rename-inline { display: flex; align-items: center; gap: var(--spacing-xs); padding-right: 2px; }
.rename-input { flex: 1; min-width: 0; height: 30px; padding: 0 8px; border: 1px solid var(--color-primary); border-radius: var(--radius-sm); font-size: 13px; font-family: inherit; outline: none; }
.rename-confirm, .rename-cancel { flex: none; width: 28px; height: 28px; border: none; border-radius: var(--radius-sm); background: transparent; color: var(--color-text-tertiary); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all .2s ease; }
.rename-confirm svg, .rename-cancel svg { width: 17px; height: 17px; }
.rename-confirm { color: var(--color-success); }
.rename-confirm:hover { background: rgba(77,214,85,.12); }
.rename-cancel:hover { background: var(--color-bg-hover); color: var(--color-danger); }
.history-meta { font-size: 11px; color: var(--color-text-tertiary); margin-top: 4px; }
.history-empty { text-align: center; color: var(--color-text-tertiary); padding: 32px 0; font-size: 13px; }
</style>
