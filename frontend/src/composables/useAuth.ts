import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

interface UserInfo {
  id: number
  username: string
  role: 'user' | 'admin'
  avatar: string
}

const currentUser = ref<UserInfo | null>(
  JSON.parse(localStorage.getItem('user_info') || 'null')
)

const isLoggedIn = computed(() => !!localStorage.getItem('auth_token'))
const isAdmin = computed(() => currentUser.value?.role === 'admin')

export function useAuth() {
  const router = useRouter()

  function setAuth(token: string, user: UserInfo) {
    localStorage.setItem('auth_token', token)
    localStorage.setItem('user_info', JSON.stringify(user))
    currentUser.value = user
  }

  function logout() {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user_info')
    currentUser.value = null
    router.push('/login')
  }

  function getToken(): string | null {
    return localStorage.getItem('auth_token')
  }

  return { currentUser, isLoggedIn, isAdmin, setAuth, logout, getToken }
}
