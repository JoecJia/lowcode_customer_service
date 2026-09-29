const BASE = '/api'

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

export async function login(username: string, password: string) {
  return authFetch(`${BASE}/login`, {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export async function register(username: string, password: string) {
  return authFetch(`${BASE}/register`, {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export async function getMe() {
  return authFetch(`${BASE}/me`)
}
