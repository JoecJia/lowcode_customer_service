const BASE = '/api'

/** 超星登录页地址（可用 VITE_PASSPORT_LOGIN_URL 覆盖） */
const PASSPORT_LOGIN_URL =
  import.meta.env.VITE_PASSPORT_LOGIN_URL || 'https://passport2.chaoxing.com/login'

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = getAuthHeaders()
  const resp = await fetch(url, {
    ...options,
    headers: { ...headers, ...(options.headers || {}) },
  })
  if (resp.status === 401) {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user_info')
    window.location.href = '/login'
  }
  return resp
}

/**
 * 构造超星登录页跳转地址。
 *
 * `refer` 只取本站 origin，不接受外部传入的任意地址，避免开放重定向。
 */
export function buildPassportLoginUrl(): string {
  const refer = `${window.location.origin}/`
  return `${PASSPORT_LOGIN_URL}?refer=${encodeURIComponent(refer)}`
}

/**
 * 用浏览器携带的超星 Cookie 换取本系统 JWT。
 *
 * 注意：这里**不使用** authFetch —— 未登录超星时返回 401 是预期结果，
 * 不能触发 authFetch 的「清 token 并跳登录页」逻辑。
 */
export async function passportLogin(): Promise<Response> {
  return fetch(`${BASE}/passport/cookie/login`, {
    method: 'POST',
    credentials: 'include',
    headers: getAuthHeaders(),
  })
}

export async function getMe() {
  return authFetch(`${BASE}/me`)
}
