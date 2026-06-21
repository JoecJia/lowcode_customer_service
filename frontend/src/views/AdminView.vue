<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import AgentConfigTab from './admin/AgentConfigTab.vue'
import FeedbackTab from './admin/FeedbackTab.vue'
import AccountTab from './admin/AccountTab.vue'

const router = useRouter()

const activeTab = ref<'agent' | 'feedback' | 'accounts'>('agent')

const adminName = computed(() => {
  const info = JSON.parse(localStorage.getItem('admin_info') || 'null')
  return info?.username || '管理员'
})

const adminInitial = computed(() => {
  return adminName.value.charAt(0).toUpperCase()
})

onMounted(() => {
  const token = localStorage.getItem('admin_token')
  const info = JSON.parse(localStorage.getItem('admin_info') || 'null')
  if (!token || !info || info.can_admin !== 1) {
    router.push('/admin/login')
  }
})

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出管理后台吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  localStorage.removeItem('admin_token')
  localStorage.removeItem('admin_info')
  router.push('/admin/login')
}

const tabs = [
  { key: 'agent' as const, label: '📂 Agent 配置' },
  { key: 'feedback' as const, label: '💬 不满意回答' },
  { key: 'accounts' as const, label: '👥 账号管理' },
]
</script>

<template>
  <div class="admin-layout">
    <!-- 顶部栏 -->
    <header class="top-bar">
      <span class="top-bar-title">低代码平台智能客服管理后台</span>
      <div class="top-bar-right">
        <span class="user-name">{{ adminName }}</span>
        <div class="user-avatar">{{ adminInitial }}</div>
        <button class="btn-logout" @click="handleLogout">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M5 2H3a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h2"/>
            <polyline points="9 10 13 7 9 4"/>
            <line x1="13" y1="7" x2="5" y2="7"/>
          </svg>
          退出
        </button>
      </div>
    </header>

    <!-- 主体 -->
    <div class="main-container">
      <!-- 侧边栏 -->
      <aside class="sidebar">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="sidebar-tab"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </aside>

      <!-- 内容区域 -->
      <main class="main-area">
        <AgentConfigTab v-if="activeTab === 'agent'" />
        <FeedbackTab v-if="activeTab === 'feedback'" />
        <AccountTab v-if="activeTab === 'accounts'" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-page);
  font-family: var(--font-family);
}

/* 顶部栏 */
.top-bar {
  height: 56px;
  min-height: 56px;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border-light);
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.top-bar-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.top-bar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-name {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-primary-light);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.btn-logout {
  height: 32px;
  padding: 0 14px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--color-text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: inherit;
  transition: all 0.2s ease;
}

.btn-logout:hover {
  color: var(--color-danger);
  border-color: var(--color-danger);
}

/* 主体 */
.main-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 侧边栏 */
.sidebar {
  width: 220px;
  min-width: 220px;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border-light);
  padding: 8px 0;
  overflow-y: auto;
}

.sidebar-tab {
  width: 100%;
  height: 48px;
  padding: 0 16px;
  background: none;
  border: none;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  text-align: left;
  font-family: inherit;
  transition: all 0.2s ease;
}

.sidebar-tab:hover {
  background: var(--color-bg-hover);
}

.sidebar-tab.active {
  background: var(--color-primary-light);
  color: var(--color-primary);
}

/* 内容区域 */
.main-area {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
