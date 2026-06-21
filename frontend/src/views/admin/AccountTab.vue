<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { getAccounts, createAccount, updateAccountPassword, updateAccountPermissions } from '../../api/admin'

interface UserRow {
  id: number
  username: string
  can_chat: number
  can_admin: number
  created_at: number
}

const users = ref<UserRow[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const searchKeyword = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

// 添加账号弹窗
const addDialogVisible = ref(false)
const addFormRef = ref<FormInstance>()
const addLoading = ref(false)
const addForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  can_chat: true,
  can_admin: false,
})

const addRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 4, max: 20, message: '用户名4-20位字符', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '只能包含字母、数字和下划线', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少需要8位', trigger: 'blur' },
    { pattern: /(?=.*[a-zA-Z])(?=.*[0-9])/, message: '密码需包含字母和数字', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: (_rule, value, cb) => {
      if (value !== addForm.password) cb(new Error('两次输入的密码不一致'))
      else cb()
    }, trigger: 'blur' },
  ],
}

// 修改密码弹窗
const pwdDialogVisible = ref(false)
const pwdFormRef = ref<FormInstance>()
const pwdLoading = ref(false)
const currentEditUser = ref<UserRow | null>(null)
const pwdForm = reactive({
  password: '',
  confirmPassword: '',
})

const pwdRules: FormRules = {
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码至少需要8位', trigger: 'blur' },
    { pattern: /(?=.*[a-zA-Z])(?=.*[0-9])/, message: '密码需包含字母和数字', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: (_rule, value, cb) => {
      if (value !== pwdForm.password) cb(new Error('两次输入的密码不一致'))
      else cb()
    }, trigger: 'blur' },
  ],
}

// 修改权限弹窗
const permDialogVisible = ref(false)
const permLoading = ref(false)
const permForm = reactive({
  can_chat: true,
  can_admin: false,
})
const isAdminAccount = ref(false)

onMounted(() => {
  loadUsers()
})

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    loadUsers()
  }, 300)
}

watch(currentPage, () => loadUsers())

async function loadUsers() {
  try {
    const params: Record<string, string> = {
      limit: String(pageSize),
      offset: String((currentPage.value - 1) * pageSize),
    }
    if (searchKeyword.value) params.search = searchKeyword.value

    const resp = await getAccounts(params)
    const data = await resp.json()
    if (data.ok) {
      users.value = data.data.users
      total.value = data.data.total
    }
  } catch {
    ElMessage.error('加载用户列表失败')
  }
}

// ===== 添加账号 =====
function showAddDialog() {
  addForm.username = ''
  addForm.password = ''
  addForm.confirmPassword = ''
  addForm.can_chat = true
  addForm.can_admin = false
  addDialogVisible.value = true
}

async function handleAddAccount() {
  if (!addFormRef.value) return
  const valid = await addFormRef.value.validate().catch(() => false)
  if (!valid) return

  addLoading.value = true
  try {
    const resp = await createAccount({
      username: addForm.username,
      password: addForm.password,
      can_chat: addForm.can_chat ? 1 : 0,
      can_admin: addForm.can_admin ? 1 : 0,
    })
    const data = await resp.json()
    if (data.ok) {
      ElMessage.success('账号添加成功')
      addDialogVisible.value = false
      loadUsers()
    } else {
      ElMessage.error(data.detail || '添加失败')
    }
  } catch {
    ElMessage.error('添加失败')
  } finally {
    addLoading.value = false
  }
}

// ===== 修改密码 =====
function showChangePwdDialog(row: UserRow) {
  currentEditUser.value = row
  pwdForm.password = ''
  pwdForm.confirmPassword = ''
  pwdDialogVisible.value = true
}

async function handleChangePwd() {
  if (!pwdFormRef.value || !currentEditUser.value) return
  const valid = await pwdFormRef.value.validate().catch(() => false)
  if (!valid) return

  pwdLoading.value = true
  try {
    const resp = await updateAccountPassword(currentEditUser.value.id, pwdForm.password)
    const data = await resp.json()
    if (data.ok) {
      ElMessage.success('密码修改成功')
      pwdDialogVisible.value = false
    } else {
      ElMessage.error(data.detail || '修改失败')
    }
  } catch {
    ElMessage.error('修改失败')
  } finally {
    pwdLoading.value = false
  }
}

// ===== 修改权限 =====
function showChangePermDialog(row: UserRow) {
  currentEditUser.value = row
  permForm.can_chat = row.can_chat === 1
  permForm.can_admin = row.can_admin === 1
  isAdminAccount.value = row.username === 'admin'
  permDialogVisible.value = true
}

async function handleChangePerm() {
  if (!currentEditUser.value) return

  permLoading.value = true
  try {
    const resp = await updateAccountPermissions(
      currentEditUser.value.id,
      permForm.can_chat ? 1 : 0,
      permForm.can_admin ? 1 : 0,
    )
    const data = await resp.json()
    if (data.ok) {
      ElMessage.success('权限修改成功')
      permDialogVisible.value = false
      loadUsers()
    } else {
      ElMessage.error(data.detail || '修改失败')
    }
  } catch {
    ElMessage.error('修改失败')
  } finally {
    permLoading.value = false
  }
}
</script>

<template>
  <div class="tab-accounts">
    <!-- 工具栏 -->
    <div class="accounts-toolbar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索用户名…"
        class="search-input"
        clearable
        @input="onSearch"
        @clear="onSearch"
      />
      <el-button type="primary" @click="showAddDialog">
        ＋ 添加账号
      </el-button>
    </div>

    <!-- 用户表格 -->
    <div class="accounts-table-wrap">
      <el-table :data="users" stripe style="width: 100%">
        <el-table-column prop="username" label="用户名" min-width="25%" />
        <el-table-column label="权限" min-width="45%">
          <template #default="{ row }">
            <span class="perm-text" :class="{ 'perm--on': row.can_chat === 1 }">
              {{ row.can_chat === 1 ? '☑ 前台' : '☐ 前台' }}
            </span>
            <span class="perm-divider">|</span>
            <span class="perm-text" :class="{ 'perm--on': row.can_admin === 1 }">
              {{ row.can_admin === 1 ? '☑ 后台' : '☐ 后台' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="30%">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showChangePwdDialog(row)">
              修改密码
            </el-button>
            <el-button type="primary" link size="small" @click="showChangePermDialog(row)">
              修改权限
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="accounts-pagination" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          background
        />
      </div>
    </div>

    <!-- 添加账号弹窗 -->
    <el-dialog v-model="addDialogVisible" title="添加账号" width="420px" :close-on-click-modal="false">
      <el-form ref="addFormRef" :model="addForm" :rules="addRules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="addForm.username" placeholder="4-20位字符" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="addForm.password" type="password" show-password placeholder="至少8位，含字母和数字" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="addForm.confirmPassword" type="password" show-password placeholder="再次输入密码" />
        </el-form-item>
        <el-form-item label="权限设置">
          <el-checkbox v-model="addForm.can_chat">前台使用权限</el-checkbox>
          <el-checkbox v-model="addForm.can_admin">后台管理权限</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="handleAddAccount">确认添加</el-button>
      </template>
    </el-dialog>

    <!-- 修改密码弹窗 -->
    <el-dialog v-model="pwdDialogVisible" title="修改密码" width="420px" :close-on-click-modal="false">
      <div v-if="currentEditUser" class="dialog-user-hint">
        用户：<strong>{{ currentEditUser.username }}</strong>
      </div>
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="80px">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="pwdForm.password" type="password" show-password placeholder="至少8位，含字母和数字" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="pwdForm.confirmPassword" type="password" show-password placeholder="再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdLoading" @click="handleChangePwd">确认修改</el-button>
      </template>
    </el-dialog>

    <!-- 修改权限弹窗 -->
    <el-dialog v-model="permDialogVisible" title="修改权限" width="420px" :close-on-click-modal="false">
      <div v-if="currentEditUser" class="dialog-user-hint">
        用户：<strong>{{ currentEditUser.username }}</strong>
      </div>
      <div class="perm-dialog-body">
        <el-checkbox v-model="permForm.can_chat">前台使用权限</el-checkbox>
        <el-checkbox
          v-model="permForm.can_admin"
          :disabled="isAdminAccount"
        >
          后台管理权限
        </el-checkbox>
        <div v-if="isAdminAccount" class="perm-hint">admin 账号不可取消后台管理权限</div>
      </div>
      <template #footer>
        <el-button @click="permDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="permLoading" @click="handleChangePerm">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tab-accounts {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px 24px;
  overflow: hidden;
}

.accounts-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.search-input {
  width: 260px;
}

.accounts-table-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.accounts-pagination {
  padding: 12px 16px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--color-border-light);
}

.perm-text {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.perm-text.perm--on {
  color: var(--color-primary);
}

.perm-divider {
  margin: 0 8px;
  color: var(--color-border);
}

.dialog-user-hint {
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--color-text-secondary);
}

.perm-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.perm-hint {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: -4px;
}
</style>
