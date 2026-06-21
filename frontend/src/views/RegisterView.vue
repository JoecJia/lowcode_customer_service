<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { register } from '../api/auth'

const router = useRouter()

const registerFormRef = ref<FormInstance>()
const loading = ref(false)
const errorMsg = ref('')

const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
})

const validateUsername = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (!value || !value.trim()) {
    return callback(new Error('请输入用户名'))
  }
  const v = value.trim()
  if (v.length < 4) return callback(new Error('用户名至少4位字符'))
  if (v.length > 20) return callback(new Error('用户名最多20位字符'))
  if (!/^[a-zA-Z0-9_]+$/.test(v)) return callback(new Error('用户名只能包含字母、数字和下划线'))
  callback()
}

const validatePassword = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (!value) return callback(new Error('请输入密码'))
  if (value.length < 8) return callback(new Error('密码至少需要8位'))
  if (!/[a-zA-Z]/.test(value) || !/[0-9]/.test(value)) return callback(new Error('密码需包含字母和数字'))
  callback()
}

const validateConfirm = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (!value) return callback(new Error('请确认密码'))
  if (value !== registerForm.password) return callback(new Error('两次输入的密码不一致'))
  callback()
}

const registerRules: FormRules = {
  username: [{ validator: validateUsername, trigger: 'blur' }],
  password: [{ validator: validatePassword, trigger: 'blur' }],
  confirmPassword: [{ validator: validateConfirm, trigger: 'blur' }],
}

function calcPasswordStrength(password: string): { level: number; label: string } {
  if (password.length < 6) return { level: 0, label: '' }
  let score = 0
  if (password.length >= 8) score++
  if (/[a-zA-Z]/.test(password) && /[0-9]/.test(password)) score++
  if (/[^a-zA-Z0-9]/.test(password)) score++
  const labels = ['', '弱', '中', '强']
  return { level: score, label: labels[score] }
}

const passwordStrength = computed(() => calcPasswordStrength(registerForm.password))

const confirmStatus = computed(() => {
  if (!registerForm.confirmPassword) return null
  return registerForm.confirmPassword === registerForm.password ? 'match' : 'mismatch'
})

const confirmText = computed(() => {
  if (confirmStatus.value === 'match') return '密码一致'
  if (confirmStatus.value === 'mismatch') return '两次输入的密码不一致'
  return ''
})

function onPasswordInput() {
  if (registerForm.confirmPassword && registerFormRef.value) {
    registerFormRef.value.validateField('confirmPassword')
  }
}

function checkConfirm() {
  if (registerFormRef.value) {
    registerFormRef.value.validateField('confirmPassword')
  }
}

function clearError() {
  errorMsg.value = ''
}

async function handleRegister() {
  if (!registerFormRef.value) return
  const valid = await registerFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''

  try {
    const resp = await register(registerForm.username.trim(), registerForm.password)
    const data = await resp.json()
    if (resp.ok) {
      ElMessage.success('注册成功，即将跳转登录页...')
      setTimeout(() => {
        router.push('/login')
      }, 800)
    } else {
      loading.value = false
      if (resp.status === 409) {
        errorMsg.value = data.detail || '用户名已被注册'
      } else {
        errorMsg.value = data.detail?.[0]?.msg || '注册失败，请稍后重试'
      }
    }
  } catch {
    errorMsg.value = '网络连接失败，请稍后重试'
    loading.value = false
  }
}
</script>

<template>
  <div class="register-page">
    <div class="decor-circle-1"></div>
    <div class="decor-circle-2"></div>

    <div class="register-card">
      <div class="brand">
        <div class="brand-logo">
          <img src="/origin.png" alt="logo" class="brand-logo-img" />
        </div>
        <div class="brand-title">创建新账号</div>
        <div class="brand-subtitle">加入智能客服平台</div>
      </div>

      <div v-if="errorMsg" class="error-msg">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke="var(--color-danger)" stroke-width="1.5"/>
          <path d="M8 4.5v4M8 11v.5" stroke="var(--color-danger)" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span>{{ errorMsg }}</span>
      </div>

      <el-form
        ref="registerFormRef"
        :model="registerForm"
        :rules="registerRules"
        label-position="top"
        @submit.prevent="handleRegister"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="registerForm.username"
            placeholder="请输入用户名（4-20位字符）"
            autocomplete="username"
            @input="clearError"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="registerForm.password"
            type="password"
            show-password
            placeholder="请输入密码（至少8位，含字母和数字）"
            autocomplete="new-password"
            @input="onPasswordInput"
          />
          <div v-if="registerForm.password" class="pwd-strength">
            <div class="pwd-strength-bar">
              <span
                v-for="n in 3"
                :key="n"
                class="bar-segment"
                :class="{
                  active: n <= passwordStrength.level,
                  weak: passwordStrength.level === 1,
                  medium: passwordStrength.level === 2,
                  strong: passwordStrength.level === 3,
                }"
              ></span>
            </div>
            <span
              class="pwd-strength-text"
              :class="{
                'text-danger': passwordStrength.level === 1,
                'text-warning': passwordStrength.level === 2,
                'text-success': passwordStrength.level === 3,
              }"
            >
              {{ passwordStrength.label ? `密码强度：${passwordStrength.label}` : '请设置安全性较高的密码' }}
            </span>
          </div>
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入密码"
            autocomplete="new-password"
            @input="checkConfirm"
          />
          <div v-if="confirmStatus" class="confirm-status" :class="confirmStatus">
            <svg v-if="confirmStatus === 'match'" width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="6" stroke="var(--color-success)" stroke-width="1.5"/>
              <path d="M4.5 7l2 2 3-4" stroke="var(--color-success)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="6" stroke="var(--color-danger)" stroke-width="1.5"/>
              <path d="M4.5 4.5l5 5M9.5 4.5l-5 5" stroke="var(--color-danger)" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <span :class="confirmStatus === 'match' ? 'text-success' : 'text-danger'">{{ confirmText }}</span>
          </div>
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="btn-submit"
          :loading="loading"
          @click="handleRegister"
        >
          {{ loading ? '注册中...' : '注 册' }}
        </el-button>
      </el-form>

      <div class="login-link">
        <router-link to="/login">已有账号？返回登录</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.register-page {
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
  width: 500px;
  height: 500px;
  top: -120px;
  left: -100px;
}

.decor-circle-2 {
  width: 350px;
  height: 350px;
  bottom: -80px;
  right: -60px;
}

.register-card {
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
  margin-bottom: 28px;
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
  margin-bottom: 18px;
}

.pwd-strength {
  margin-top: 8px;
}

.pwd-strength-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 4px;
}

.bar-segment {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: var(--color-border-light);
  transition: background 0.3s;
}

.bar-segment.active.weak {
  background: var(--color-danger);
}

.bar-segment.active.medium {
  background: var(--color-warning);
}

.bar-segment.active.strong {
  background: var(--color-success);
}

.pwd-strength-text {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.text-danger {
  color: var(--color-danger) !important;
}

.text-warning {
  color: var(--color-warning) !important;
}

.text-success {
  color: var(--color-success) !important;
}

.confirm-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  margin-top: 6px;
}

.confirm-status.match span {
  color: var(--color-success);
}

.confirm-status.mismatch span {
  color: var(--color-danger);
}

.btn-submit {
  width: 100%;
  height: 40px;
  font-size: 16px;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, #2B67FF 0%, #3D82F2 100%);
  border: none;
}

.login-link {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
}

.login-link a {
  color: var(--color-primary);
  text-decoration: none;
}

.login-link a:hover {
  color: var(--color-primary-hover);
}
</style>
