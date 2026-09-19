<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { buildPassportLoginUrl, passportLogin } from '../../api/auth'
import { clearLoggedOutFlag } from '../../composables/useAuth'

const router = useRouter()

const loading = ref(false)
const errorMsg = ref('')

onMounted(async () => {
  const token = localStorage.getItem('admin_token')
  if (token) {
    try {
      const info = JSON.parse(localStorage.getItem('admin_info') || 'null')
      if (info && info.can_admin === 1) {
        router.push('/admin')
        return
      }
    } catch { /* not logged in */ }
  }
  await tryAdminLogin()
})

/** 用超星登录态换取管理后台 token，并校验后台管理权限 */
async function tryAdminLogin() {
  loading.value = true
  errorMsg.value = ''

  try {
    const resp = await passportLogin()
    if (!resp.ok) {
      errorMsg.value = '未检测到超星登录状态，请先登录超星账号'
      return
    }

    const data = await resp.json()
    if (!data?.user) {
      errorMsg.value = '登录失败，请稍后重试'
      return
    }
    if (data.user.can_admin !== 1) {
      errorMsg.value = '无管理权限，登录失败'
      return
    }

    clearLoggedOutFlag()
    localStorage.setItem('admin_token', data.access_token)
    localStorage.setItem('admin_info', JSON.stringify(data.user))
    ElMessage.success('登录成功')
    router.push('/admin')
  } catch {
    errorMsg.value = '网络连接失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

/** 跳转超星登录页（refer 为本站地址，登录成功后回跳） */
function handlePassportLogin() {
  clearLoggedOutFlag()
  window.location.href = buildPassportLoginUrl()
}
</script>

<template>
  <div class="admin-login-page">
    <div class="decor-circle decor-circle-1"></div>
    <div class="decor-circle decor-circle-2"></div>

    <div class="login-card">
      <!-- 标题 -->
      <div class="brand">
        <div class="brand-logo">
          <img src="/origin.png" alt="logo" class="brand-logo-img" />
        </div>
        <h1 class="brand-title">低代码平台智能客服管理后台</h1>
        <p class="brand-subtitle">使用超星账号登录</p>
      </div>

      <!-- 错误提示 -->
      <div v-if="errorMsg" class="error-msg">
        <svg viewBox="0 0 16 16" fill="currentColor" width="16" height="16">
          <path d="M8 1a7 7 0 1 1 0 14A7 7 0 0 1 8 1zm0 10a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5zM7.25 5v4a.75.75 0 0 0 1.5 0V5a.75.75 0 0 0-1.5 0z"/>
        </svg>
        <span>{{ errorMsg }}</span>
      </div>

      <div v-if="loading" class="checking-hint">正在检测超星登录状态...</div>

      <!-- 登录按钮 -->
      <el-button
        type="primary"
        size="large"
        class="btn-login"
        @click="handlePassportLogin"
      >
        使用超星账号登录
      </el-button>

      <div class="login-tip">
        仅具备后台管理权限的账号可进入，
        <a href="javascript:void(0)" @click="tryAdminLogin">重新检测登录状态</a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #2B67FF 0%, #5B8CFF 100%);
  font-family: var(--font-family);
}

.decor-circle {
  position: fixed;
  border-radius: 50%;
  opacity: 0.06;
  pointer-events: none;
  background: #fff;
}

.decor-circle-1 {
  width: 600px;
  height: 600px;
  top: -200px;
  right: -150px;
}

.decor-circle-2 {
  width: 400px;
  height: 400px;
  bottom: -100px;
  left: -100px;
}

.login-card {
  position: relative;
  z-index: 1;
  width: 400px;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: 40px;
}

.brand {
  text-align: center;
  margin-bottom: 32px;
}

.brand-logo {
  width: 48px;
  height: 48px;
  margin: 0 auto 16px;
}

.brand-logo-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.brand-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 28px;
}

.brand-subtitle {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.error-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #FFF0F0;
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  margin-bottom: 20px;
  font-size: 13px;
  color: var(--color-danger);
  line-height: 20px;
}

.error-msg svg {
  flex-shrink: 0;
}

.checking-hint {
  font-size: 13px;
  color: var(--color-text-tertiary);
  text-align: center;
  margin-bottom: 16px;
}

.btn-login {
  width: 100%;
  height: 40px;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 0.5px;
  margin-top: 4px;
}

.login-tip {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  line-height: 20px;
  color: var(--color-text-tertiary);
}

.login-tip a {
  color: var(--color-primary);
  text-decoration: none;
}
</style>
