import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { passportLogin } from '../api/auth'

export interface UserInfo {
  id: number
  username: string
  role: 'user' | 'admin'
  avatar: string
  can_chat?: number
  can_admin?: number
  uid?: string
  fid?: string
  realname?: string
}

/** 主动退出标志位：置位后不再自动静默登录，直到用户手动点击「使用超星账号登录」 */
const LOGOUT_FLAG_KEY = 'passport_logout_flag'

const currentUser = ref<UserInfo | null>(
  JSON.parse(localStorage.getItem('user_info') || 'null')
)

const isLoggedIn = computed(() => !!localStorage.getItem('auth_token'))
const isAdmin = computed(() => currentUser.value?.role === 'admin')

export function hasLoggedOutFlag(): boolean {
  return localStorage.getItem(LOGOUT_FLAG_KEY) === '1'
}

export function setLoggedOutFlag(): void {
  localStorage.setItem(LOGOUT_FLAG_KEY, '1')
}

export function clearLoggedOutFlag(): void {
  localStorage.removeItem(LOGOUT_FLAG_KEY)
}

export function displayName(user: UserInfo | null): string {
  return user?.realname || user?.username || ''
}

function persistAuth(token: string, user: UserInfo) {
  localStorage.setItem('auth_token', token)
  localStorage.setItem('user_info', JSON.stringify(user))
  currentUser.value = user
}

function clearAuth() {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('user_info')
  currentUser.value = null
}

/** 静默登录结果的短时缓存，避免启动引导与登录页各发一次请求 */
let lastAttempt: { at: number; ok: boolean } | null = null
const ATTEMPT_COOLDOWN_MS = 3000

/**
 * 启动引导：本地无 token 且用户未主动退出时，用超星 Cookie 静默换取 JWT。
 *
 * @returns 是否已处于登录态
 */
export async function bootstrapPassportLogin(): Promise<boolean> {
  if (localStorage.getItem('auth_token')) return true
  if (hasLoggedOutFlag()) return false

  if (lastAttempt && Date.now() - lastAttempt.at < ATTEMPT_COOLDOWN_MS) {
    return lastAttempt.ok
  }

  let ok = false
  try {
    const resp = await passportLogin()
    if (resp.ok) {
      const data = await resp.json()
      if (data?.access_token && data?.user) {
        persistAuth(data.access_token, data.user)
        ok = true
      }
    }
  } catch {
    ok = false
  }

  lastAttempt = { at: Date.now(), ok }
  return ok
}

export function useAuth() {
  const router = useRouter()

  function setAuth(token: string, user: UserInfo) {
    persistAuth(token, user)
  }

  function logout() {
    // 只清本地登录态；超星 passport 的登录态不在本系统可控范围内，
    // 因此写入标志位，避免刷新后被自动登录回来。
    setLoggedOutFlag()
    clearAuth()
    router.push('/login')
  }

  function getToken(): string | null {
    return localStorage.getItem('auth_token')
  }

  return { currentUser, isLoggedIn, isAdmin, setAuth, logout, getToken, displayName }
}
