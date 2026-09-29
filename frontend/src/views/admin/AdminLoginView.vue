<script setup lang="ts">
import { reactive, ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()

const loginFormRef = ref<FormInstance>()
const loading = ref(false)
const errorMsg = ref('')

const loginForm = reactive({
  username: '',
  password: '',
})

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

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
  await nextTick()
  document.getElementById('admin-username')?.focus()
})

function clearError() {
  errorMsg.value = ''
}

async function handleLogin() {
  if (!loginFormRef.value) return

  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''

  try {
    const resp = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: loginForm.username,
        password: loginForm.password,
      }),
    })

    const data = await resp.json()

    if (resp.ok && data.ok && data.user) {
      if (data.user.can_admin !== 1) {
        errorMsg.value = '无管理权限，登录失败'
        loading.value = false
        return
      }

      localStorage.setItem('admin_token', data.access_token)
      localStorage.setItem('admin_info', JSON.stringify(data.user))
      ElMessage.success('登录成功')
      router.push('/admin')
    } else {
      errorMsg.value = '用户名或密码错误'
    }
  } catch {
    errorMsg.value = '网络连接失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

// 密码仅允许 ASCII 字符（字母、数字、符号）
function filterPasswordInput(val: string) {
  clearError()
  loginForm.password = val.replace(/[^\x20-\x7e]/g, '')
}

// 密码框 Enter：仅当账号密码都齐全且非 IME 组合输入时触发登录
function onPasswordEnter(e: KeyboardEvent) {
  if (e.isComposing) return
  if (loginForm.username.trim() && loginForm.password.trim()) {
    handleLogin()
  }
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
        <p class="brand-subtitle">管理员登录</p>
      </div>

      <!-- 错误提示 -->
      <div v-if="errorMsg" class="error-msg">
        <svg viewBox="0 0 16 16" fill="currentColor" width="16" height="16">
          <path d="M8 1a7 7 0 1 1 0 14A7 7 0 0 1 8 1zm0 10a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5zM7.25 5v4a.75.75 0 0 0 1.5 0V5a.75.75 0 0 0-1.5 0z"/>
        </svg>
        <span>{{ errorMsg }}</span>
      </div>

      <!-- 表单 -->
      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username" label="用户名">
          <el-input
            id="admin-username"
            v-model="loginForm.username"
            placeholder="请输入用户名"
            autocomplete="username"
            @input="clearError"
          />
        </el-form-item>

        <el-form-item prop="password" label="密码">
          <el-input
            id="admin-password"
            v-model="loginForm.password"
            type="password"
            show-password
            placeholder="请输入密码"
            autocomplete="current-password"
            @input="filterPasswordInput"
            @keydown.enter="onPasswordEnter"
          />
        </el-form-item>
      </el-form>

      <!-- 登录按钮 -->
      <el-button
        type="primary"
        size="large"
        class="btn-login"
        :loading="loading"
        @click="handleLogin"
      >
        {{ loading ? '登录中...' : '登 录' }}
      </el-button>

      <!-- 底部提示 -->
      <div class="register-link">
        管理后台不支持自主注册，请联系超级管理员
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

.btn-login {
  width: 100%;
  height: 40px;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 0.5px;
  margin-top: 4px;
}

.register-link {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
  color: var(--color-text-tertiary);
}
</style>
