<script setup lang="ts">
import { ref } from 'vue'
import type { ContextChange } from '../composables/useMaintenanceChat'

defineProps<{ item: ContextChange }>()
const expanded = ref(false)

function diffLines(diff: string): { kind: 'add' | 'del' | 'ctx' | 'meta'; text: string }[] {
  const out: { kind: 'add' | 'del' | 'ctx' | 'meta'; text: string }[] = []
  for (const line of (diff || '').split('\n')) {
    if (line.startsWith('+++') || line.startsWith('---')) out.push({ kind: 'meta', text: line })
    else if (line.startsWith('+')) out.push({ kind: 'add', text: line })
    else if (line.startsWith('-')) out.push({ kind: 'del', text: line })
    else out.push({ kind: 'ctx', text: line })
  }
  return out
}
</script>

<template>
  <div class="change-card">
    <div class="change-header">
      <span class="change-icon">{{ item.op === 'create' ? '＋' : '✎' }}</span>
      <span class="change-target">{{ item.target }}</span>
      <span class="change-index">#{{ item.item_index + 1 }}/{{ item.item_count }}</span>
    </div>
    <div class="change-summary">{{ item.summary }}</div>
    <button class="diff-toggle" @click="expanded = !expanded">{{ expanded ? '收起差异' : '查看差异' }}</button>
    <div v-if="expanded" class="change-diff">
      <div v-for="(l, i) in diffLines(item.diff)" :key="i" class="diff-line" :class="l.kind">{{ l.text }}</div>
    </div>
  </div>
</template>

<style scoped>
.change-card { border: 1px solid var(--color-border-light); border-radius: var(--radius-sm); background: var(--color-bg-card); padding: 8px 10px; margin: 6px 0; }
.change-header { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.change-icon { color: var(--color-primary); font-weight: 700; }
.change-target { font-family: monospace; color: var(--color-text-primary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.change-index { color: var(--color-text-tertiary); }
.change-summary { font-size: 12px; color: var(--color-text-secondary); margin: 4px 0; }
.diff-toggle { border: none; background: transparent; color: var(--color-primary); cursor: pointer; font-size: 11px; padding: 0; }
.change-diff { margin-top: 6px; max-height: 240px; overflow-y: auto; background: var(--color-bg-page); border-radius: var(--radius-sm); padding: 6px; }
.diff-line { font-family: monospace; font-size: 11px; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
.diff-line.add { color: #1a7f37; background: rgba(26,127,55,.08); }
.diff-line.del { color: #cf222e; background: rgba(207,34,46,.08); }
.diff-line.meta { color: var(--color-text-tertiary); }
.diff-line.ctx { color: var(--color-text-secondary); }
</style>
