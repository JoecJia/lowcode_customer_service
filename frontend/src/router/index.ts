import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: () => import('../views/ChatView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/RegisterView.vue'),
      meta: { guest: true },
    },
    {
      path: '/admin/login',
      name: 'adminLogin',
      component: () => import('../views/admin/AdminLoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
      meta: { requiresAdmin: true },
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const authToken = localStorage.getItem('auth_token')
  const adminToken = localStorage.getItem('admin_token')

  // ===== 管理端路由 =====
  if (to.path.startsWith('/admin')) {
    // /admin/login: 已登录管理员 → 跳转 /admin
    if (to.path === '/admin/login') {
      if (adminToken) {
        try {
          const adminInfo = JSON.parse(localStorage.getItem('admin_info') || 'null')
          if (adminInfo && adminInfo.can_admin === 1) {
            return next('/admin')
          }
        } catch { /* fall through */ }
      }
      return next()
    }

    // /admin (后台主页): 需要 admin_token + can_admin == 1
    if (!adminToken) {
      return next('/admin/login')
    }
    try {
      const adminInfo = JSON.parse(localStorage.getItem('admin_info') || 'null')
      if (!adminInfo || adminInfo.can_admin !== 1) {
        localStorage.removeItem('admin_token')
        localStorage.removeItem('admin_info')
        return next('/admin/login')
      }
    } catch {
      return next('/admin/login')
    }
    return next()
  }

  // ===== 用户前台路由（已有逻辑） =====
  const token = authToken

  if (to.meta.guest) {
    if (token) {
      return next('/')
    }
    return next()
  }

  if (to.meta.requiresAuth) {
    if (!token) {
      return next('/login')
    }
  }

  next()
})

export default router
