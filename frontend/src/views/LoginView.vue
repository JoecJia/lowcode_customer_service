<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { buildPassportLoginUrl } from '../api/auth'
import {
  bootstrapPassportLogin,
  clearLoggedOutFlag,
  hasLoggedOutFlag,
  useAuth,
} from '../composables/useAuth'

const router = useRouter()
const auth = useAuth()

/** 是否正在静默检测超星登录态 */
const checking = ref(true)
const errorMsg = ref('')

onMounted(async () => {
  // 本地已有 token 直接进入
  if (auth.getToken()) {
    router.push('/')
    return
  }

  // 用户主动退出过 → 不再自动登录，等待手动点击
  if (hasLoggedOutFlag()) {
    errorMsg.value = '您已退出登录，可重新使用超星账号登录'
    checking.value = false
    return
  }

  const ok = await bootstrapPassportLogin()
  if (ok) {
    router.push('/')
    return
  }

  errorMsg.value = '未检测到超星登录状态，请先登录超星账号'
  checking.value = false
})

/** 跳转超星登录页（refer 为本站地址，登录成功后回跳） */
function handlePassportLogin() {
  clearLoggedOutFlag()
  window.location.href = buildPassportLoginUrl()
}
</script>

<template>
  <div class="login-page">
    <div class="decor-circle-1"></div>
    <div class="decor-circle-2"></div>

    <div class="login-card">
      <div class="brand">
        <div class="brand-logo">
          <img src="/origin.png" alt="logo" class="brand-logo-img" />
        </div>
        <div class="brand-title">低代码平台智能客服</div>
        <div class="brand-subtitle">使用超星账号登录</div>
      </div>

      <div v-if="errorMsg" class="error-msg">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke="var(--color-danger)" stroke-width="1.5"/>
          <path d="M8 4.5v4M8 11v.5" stroke="var(--color-danger)" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span>{{ errorMsg }}</span>
      </div>

      <div v-if="checking" class="checking-hint">正在检测超星登录状态...</div>

      <el-button
        type="primary"
        size="large"
        class="btn-submit"
        @click="handlePassportLogin"
      >
        使用超星账号登录
      </el-button>

      <div class="login-tip">点击后将跳转超星登录页，登录成功后自动返回本站</div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #2B67FF 0%, #5B8CFF 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.decor-circle-1,
.decor-circle-2 {
  position: fixed;
  border-radius: 50%;
  background: #fff;
  opacity: 0.06;
  pointer-events: none;
}

.decor-circle-1 {
  width: 600px;
  height: 600px;
  top: -200px;
  right: -100px;
}

.decor-circle-2 {
  width: 400px;
  height: 400px;
  bottom: -150px;
  left: -80px;
}

.login-card {
  width: 400px;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: 40px;
  position: relative;
  z-index: 1;
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
  margin-bottom: 6px;
}

.brand-subtitle {
  font-size: 14px;
  color: var(--color-text-tertiary);
}

.error-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #FFF0F0;
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  font-size: 13px;
  color: var(--color-danger);
  margin-bottom: 20px;
}

.checking-hint {
  font-size: 13px;
  color: var(--color-text-tertiary);
  text-align: center;
  margin-bottom: 16px;
}

.btn-submit {
  width: 100%;
  height: 40px;
  font-size: 16px;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, #2B67FF 0%, #3D82F2 100%);
  border: none;
}

.login-tip {
  text-align: center;
  margin-top: 16px;
  font-size: 12px;
  line-height: 18px;
  color: var(--color-text-tertiary);
}
</style>
