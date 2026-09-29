<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { login } from '../api/auth'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const auth = useAuth()

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

onMounted(() => {
  if (auth.getToken()) {
    router.push('/')
    return
  }
  nextTick(() => {
    const el = document.querySelector('.login-card input') as HTMLInputElement
    el?.focus()
  })
})

function clearError() {
  errorMsg.value = ''
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

async function handleLogin() {
  if (!loginFormRef.value) return
  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''

  try {
    const resp = await login(loginForm.username.trim(), loginForm.password)
    const data = await resp.json()
    if (resp.ok) {
      auth.setAuth(data.access_token, data.user)
      ElMessage.success('登录成功')
      router.push('/')
    } else {
      errorMsg.value = data.detail || '用户名或密码错误'
      loading.value = false
    }
  } catch {
    errorMsg.value = '网络连接失败，请稍后重试'
    loading.value = false
  }
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
        <div class="brand-subtitle">登录您的账号</div>
      </div>

      <div v-if="errorMsg" class="error-msg">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke="var(--color-danger)" stroke-width="1.5"/>
          <path d="M8 4.5v4M8 11v.5" stroke="var(--color-danger)" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span>{{ errorMsg }}</span>
      </div>

      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="请输入用户名"
            autocomplete="username"
            @input="clearError"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            show-password
            placeholder="请输入密码"
            autocomplete="current-password"
            @input="filterPasswordInput"
            @keydown.enter="onPasswordEnter"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="btn-submit"
          :loading="loading"
          @click="handleLogin"
        >
          {{ loading ? '登录中...' : '登 录' }}
        </el-button>
      </el-form>

      <div class="register-link">
        <router-link to="/register">还没有账号？立即注册</router-link>
      </div>
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

.btn-submit {
  width: 100%;
  height: 40px;
  font-size: 16px;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, #2B67FF 0%, #3D82F2 100%);
  border: none;
}

.register-link {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
}

.register-link a {
  color: var(--color-primary);
  text-decoration: none;
}

.register-link a:hover {
  color: var(--color-primary-hover);
}
</style>
