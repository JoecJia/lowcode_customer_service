<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { getAgentConfigTree, getAgentConfigFile } from '../../api/admin'

interface TreeNode {
  name: string
  type: 'file' | 'folder'
  ext?: string
  path: string
  previewable?: boolean
  children?: TreeNode[]
}

const treeData = ref<TreeNode[]>([])
const currentFilePath = ref('')
const currentFileContent = ref('')
const loadingContent = ref(false)
const treeRef = ref<any>(null)

const treeProps = {
  children: 'children',
  label: 'name',
}

onMounted(async () => {
  try {
    const resp = await getAgentConfigTree()
    const data = await resp.json()
    if (data.ok) {
      treeData.value = data.data.tree
      await nextTick()
      // 默认展开第一层
      if (treeRef.value) {
        const rootNodes = treeData.value
        for (const node of rootNodes) {
          treeRef.value.store.nodesMap[node.path]?.expand()
        }
      }
    }
  } catch {
    ElMessage.error('加载文件树失败')
  }
})

function isPreviewable(node: TreeNode): boolean {
  return node.previewable !== false
}

async function onNodeClick(node: TreeNode) {
  if (node.type === 'folder') return
  if (!isPreviewable(node)) return

  currentFilePath.value = node.path
  currentFileContent.value = ''
  loadingContent.value = true

  try {
    const resp = await getAgentConfigFile(node.path)
    const data = await resp.json()
    if (data.ok && data.data) {
      currentFileContent.value = data.data.content
    } else {
      ElMessage.error('文件不存在或不可预览')
    }
  } catch {
    ElMessage.error('加载文件失败')
  } finally {
    loadingContent.value = false
  }
}

function renderMarkdown(raw: string): string {
  return marked.parse(raw, { breaks: true }) as string
}
</script>

<template>
  <div class="tab-agent">
    <!-- 左侧文件树 -->
    <div class="file-tree-panel">
      <div class="tree-header">agent_config/</div>
      <el-tree
        ref="treeRef"
        :data="treeData"
        :props="treeProps"
        node-key="path"
        highlight-current
        @node-click="onNodeClick"
      >
        <template #default="{ data }">
          <span
            class="tree-node"
            :class="{
              'tree-node--folder': data.type === 'folder',
              'tree-node--no-preview': data.type === 'file' && !isPreviewable(data),
            }"
          >
            <span class="tree-node-icon">
              {{ data.type === 'folder' ? '📁' : '📄' }}
            </span>
            <span class="tree-node-label">{{ data.name }}</span>
          </span>
        </template>
      </el-tree>
    </div>

    <!-- 右侧预览区 -->
    <div class="md-preview-panel">
      <template v-if="!currentFilePath">
        <div class="md-placeholder">请在左侧选择文件进行预览</div>
      </template>
      <template v-else>
        <div class="md-file-title">{{ currentFilePath }}</div>
        <div class="md-content" v-loading="loadingContent">
          <div v-if="currentFileContent" v-html="renderMarkdown(currentFileContent)" class="markdown-body"></div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.tab-agent {
  display: flex;
  height: 100%;
}

/* 文件树 */
.file-tree-panel {
  width: 300px;
  min-width: 240px;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border-light);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.tree-header {
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border-light);
}

.file-tree-panel :deep(.el-tree) {
  padding: 8px 0;
  background: transparent;
}

.file-tree-panel :deep(.el-tree-node__content) {
  height: 32px;
  padding-right: 8px;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text-primary);
}

.tree-node--no-preview {
  color: var(--color-text-disabled);
  cursor: not-allowed;
}

.tree-node-icon {
  font-size: 14px;
}

.tree-node-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 预览区 */
.md-preview-panel {
  flex: 1;
  overflow-y: auto;
  background: var(--color-bg-card);
  margin: 12px;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
}

.md-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: var(--color-text-tertiary);
}

.md-file-title {
  padding: 12px 20px;
  font-size: 13px;
  color: var(--color-text-tertiary);
  border-bottom: 1px solid var(--color-border-light);
  font-family: monospace;
  flex-shrink: 0;
}

.md-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text-primary);
}

.markdown-body :deep(h1) { font-size: 24px; font-weight: 600; margin: 24px 0 12px; }
.markdown-body :deep(h2) { font-size: 20px; font-weight: 600; margin: 20px 0 10px; }
.markdown-body :deep(h3) { font-size: 16px; font-weight: 600; margin: 16px 0 8px; }
.markdown-body :deep(p) { margin: 8px 0; }
.markdown-body :deep(code) {
  background: var(--color-bg-page);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 13px;
}
.markdown-body :deep(pre) {
  background: var(--color-bg-page);
  padding: 12px 16px;
  border-radius: var(--radius-md);
  overflow-x: auto;
  font-size: 13px;
  margin: 8px 0;
}
.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
}
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 20px; margin: 8px 0; }
.markdown-body :deep(li) { margin: 4px 0; }
.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--color-primary);
  padding-left: 12px;
  color: var(--color-text-secondary);
  margin: 8px 0;
}
.markdown-body :deep(a) { color: var(--color-primary); }
.markdown-body :deep(table) { border-collapse: collapse; width: 100%; margin: 8px 0; }
.markdown-body :deep(th), .markdown-body :deep(td) {
  border: 1px solid var(--color-border);
  padding: 8px 12px;
  text-align: left;
}
.markdown-body :deep(th) { background: var(--color-bg-page); font-weight: 600; }
</style>
