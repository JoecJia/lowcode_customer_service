const BASE = '/api/admin'

function getAdminAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('admin_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

export async function adminAuthFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = getAdminAuthHeaders()
  const resp = await fetch(url, {
    ...options,
    headers: { ...headers, ...(options.headers || {}) },
  })
  if (resp.status === 401) {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_info')
    window.location.href = '/admin/login'
  }
  return resp
}

// 反馈
export async function getFeedbacks(params: Record<string, string>) {
  const qs = new URLSearchParams(params).toString()
  return adminAuthFetch(`${BASE}/feedbacks?${qs}`)
}

export async function getFeedbackDetail(id: number) {
  return adminAuthFetch(`${BASE}/feedbacks/${id}`)
}

export async function resolveFeedback(id: number, qa_pairs: { question: string; answer: string }[]) {
  return adminAuthFetch(`${BASE}/feedbacks/${id}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ qa_pairs }),
  })
}

// Agent 配置
export async function getAgentConfigTree() {
  return adminAuthFetch(`${BASE}/agent-config/tree`)
}

export async function getAgentConfigFile(path: string) {
  const qs = new URLSearchParams({ path }).toString()
  return adminAuthFetch(`${BASE}/agent-config/file?${qs}`)
}

// 账号管理
export async function getAccounts(params: Record<string, string>) {
  const qs = new URLSearchParams(params).toString()
  return adminAuthFetch(`${BASE}/accounts?${qs}`)
}

export async function createAccount(data: Record<string, unknown>) {
  return adminAuthFetch(`${BASE}/accounts`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateAccountPassword(userId: number, password: string) {
  return adminAuthFetch(`${BASE}/accounts/${userId}/password`, {
    method: 'PATCH',
    body: JSON.stringify({ password }),
  })
}

export async function updateAccountPermissions(userId: number, can_chat: number, can_admin: number) {
  return adminAuthFetch(`${BASE}/accounts/${userId}/permissions`, {
    method: 'PATCH',
    body: JSON.stringify({ can_chat, can_admin }),
  })
}
