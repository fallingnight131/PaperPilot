<template>
  <div class="layout">
    <!-- 顶部导航栏 -->
    <el-header class="header">
      <div class="header-left">
        <h2 class="logo" @click="$router.push('/home')" style="cursor:pointer">📚 PaperPilot</h2>
      </div>
      <el-menu mode="horizontal" default-active="/history" router class="nav-menu">
        <el-menu-item index="/home"><el-icon><HomeFilled /></el-icon>首页</el-menu-item>
        <el-menu-item index="/documents"><el-icon><Document /></el-icon>文献管理</el-menu-item>
        <el-menu-item index="/library"><el-icon><Collection /></el-icon>文献库</el-menu-item>
        <el-menu-item index="/knowledge"><el-icon><DataAnalysis /></el-icon>知识库</el-menu-item>
        <el-menu-item index="/chat"><el-icon><ChatDotRound /></el-icon>智能问答</el-menu-item>
        <el-menu-item index="/history"><el-icon><Clock /></el-icon>会话历史</el-menu-item>
      </el-menu>
      <div class="header-right">
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-avatar :size="32" icon="UserFilled" />
            <span class="username">{{ authStore.currentUser?.username }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <el-main class="main-content">
      <h2 class="page-title">会话历史</h2>

      <el-table :data="conversations" stripe style="width: 100%">
        <el-table-column prop="title" label="会话标题" min-width="300" show-overflow-tooltip />
        <el-table-column prop="message_count" label="消息数" width="100" align="center" />
        <el-table-column label="创建时间" width="200">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="最后更新" width="200">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="openConversation(row.id)">继续对话</el-button>
            <el-button size="small" type="danger" @click="deleteConversation(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="conversations.length === 0" description="暂无会话历史" />
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'

const router = useRouter()
const authStore = useAuthStore()
const chatStore = useChatStore()

const conversations = ref([])

const handleCommand = (command) => {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const openConversation = (convId) => {
  router.push({ path: '/chat', query: { conversation_id: convId } })
}

const deleteConversation = async (convId) => {
  try {
    await ElMessageBox.confirm('确定要删除此会话吗？', '提示', { type: 'warning' })
    await chatStore.deleteConversation(convId)
    conversations.value = conversations.value.filter((c) => c.id !== convId)
    ElMessage.success('会话已删除')
  } catch {
    // 取消
  }
}

onMounted(async () => {
  await chatStore.fetchConversations()
  conversations.value = chatStore.conversations
})
</script>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  align-items: center;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  padding: 0 24px;
  height: 60px;
  z-index: 100;
}

.header-left { display: flex; align-items: center; }
.logo { font-size: 20px; color: #409eff; white-space: nowrap; margin-right: 40px; }
.nav-menu { flex: 1; border-bottom: none; }
.header-right { display: flex; align-items: center; }
.user-info { display: flex; align-items: center; cursor: pointer; gap: 8px; }
.username { font-size: 14px; color: #606266; }

.main-content {
  flex: 1;
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.page-title {
  margin-bottom: 24px;
  color: #303133;
}
</style>
