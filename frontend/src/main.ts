import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
// 全局弹层初始 z-index 提到 3000：后台维护助手抽屉为 2500，
// Element Plus 默认从 2000 起算，会导致确认弹窗/提示被抽屉盖住。
app.use(ElementPlus, { zIndex: 3000 })
app.use(router)
app.mount('#app')
