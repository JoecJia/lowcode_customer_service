import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import { bootstrapPassportLogin } from './composables/useAuth'
import './style.css'

const app = createApp(App)
app.use(ElementPlus)
app.use(router)

// 启动引导：已登录超星且本地无 token 时先静默换取 JWT，
// 让已登录用户直接进入对话页、避免登录页闪现。
bootstrapPassportLogin().finally(() => {
  app.mount('#app')
})
