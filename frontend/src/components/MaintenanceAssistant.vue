<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import MaintenanceChatDialog from './MaintenanceChatDialog.vue'

const expanded = ref(false)
const enabled = ref(false)

// 抽屉宽度可拖拽调整（贴右侧，左移变宽）
const drawerWidth = ref(480)
const MIN_WIDTH = 320
const isResizing = ref(false)
let resizeStartX = 0
let resizeStartWidth = 480

function onResizeStart(e: MouseEvent) {
  e.preventDefault()
  isResizing.value = true
  resizeStartX = e.clientX
  resizeStartWidth = drawerWidth.value
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', onResizeEnd)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}
function onResizeMove(e: MouseEvent) {
  if (!isResizing.value) return
  const delta = resizeStartX - e.clientX
  drawerWidth.value = Math.max(MIN_WIDTH, Math.min(window.innerWidth - 120, resizeStartWidth + delta))
}
function onResizeEnd() {
  if (!isResizing.value) return
  isResizing.value = false
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}
onBeforeUnmount(onResizeEnd)

onMounted(async () => {
  // 灰度开关：通过读取能否拉取后台会话列表判断（403 则隐藏入口）
  try {
    const resp = await fetch('/api/admin/sessions?limit=1', {
      headers: { Authorization: `Bearer ${localStorage.getItem('admin_token') || ''}` },
    })
    enabled.value = resp.status !== 403 && resp.status !== 401
  } catch { enabled.value = false }
})
</script>

<template>
  <div v-if="enabled">
    <!-- 收起态：右下角悬浮球 -->
    <button v-if="!expanded" class="fab" title="后台维护助手" @click="expanded = true">
      <img src="/ai-assistant.svg" alt="维护助手" />
    </button>

    <!-- 展开态：右侧抽屉 + 遮罩层 -->
    <Transition name="drawer">
      <div v-if="expanded" class="drawer-layer">
        <div class="drawer-mask" @click="expanded = false"></div>
        <aside class="drawer" :style="{ width: drawerWidth + 'px' }">
          <div class="drawer-resizer" title="拖动调整宽度" @mousedown.prevent="onResizeStart"></div>
          <MaintenanceChatDialog @collapse="expanded = false" />
        </aside>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* 悬浮球 */
.fab { position: fixed; right: 24px; bottom: 24px; z-index: 2500; width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--color-border-light); background: var(--color-bg-card); color: #fff; cursor: pointer; box-shadow: 0 4px 16px rgba(0,0,0,.14); display: flex; align-items: center; justify-content: center; transition: box-shadow .2s ease, transform .2s ease; }
.fab:hover { box-shadow: 0 6px 20px rgba(0,0,0,.2); transform: translateY(-2px); }
.fab img { width: 28px; height: 28px; object-fit: contain; }

/* 抽屉层：遮罩贴满视口，抽屉贴右侧、占满高度 */
.drawer-layer { position: fixed; inset: 0; z-index: 2500; }
.drawer-mask { position: absolute; inset: 0; background: rgba(0,0,0,.45); }
.drawer {
  position: absolute; top: 0; right: 0; bottom: 0;
  width: 480px; max-width: 100vw;
  background: var(--color-bg-card);
  box-shadow: var(--shadow-lg);
  display: flex;
}
/* 左边缘拖拽手柄：hover 显示主色竖条，提示可拖动 */
.drawer-resizer { position: absolute; left: 0; top: 0; bottom: 0; width: 8px; cursor: col-resize; z-index: 2; transition: background .2s; }
.drawer-resizer:hover { background: var(--color-primary); }
.drawer :deep(.dialog) { flex: 1; min-width: 0; }

/* 遮罩淡入 + 抽屉从右滑入（0.3s ease，符合设计规范动效） */
.drawer-enter-active, .drawer-leave-active { transition: opacity .3s ease; }
.drawer-enter-active .drawer, .drawer-leave-active .drawer { transition: transform .3s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer, .drawer-leave-to .drawer { transform: translateX(100%); }
</style>
