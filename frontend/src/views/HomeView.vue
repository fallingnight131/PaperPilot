<template>
  <div class="layout">
    <!-- 顶部导航栏 -->
    <el-header class="header">
      <div class="header-left">
        <h2 class="logo">📚 PaperPilot</h2>
      </div>
      <el-menu mode="horizontal" :default-active="activeMenu" router class="nav-menu">
        <el-menu-item index="/home">
          <el-icon><HomeFilled /></el-icon>首页
        </el-menu-item>
        <el-menu-item index="/documents">
          <el-icon><Document /></el-icon>文献管理
        </el-menu-item>
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>智能问答
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><Clock /></el-icon>会话历史
        </el-menu-item>
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

    <!-- 主内容区 -->
    <el-main class="main-content">
      <div class="welcome-section">
        <h1>欢迎使用 PaperPilot</h1>
        <p>面向电化学储能材料领域的智能文献问答平台</p>
      </div>

      <el-row :gutter="24" class="feature-cards">
        <el-col :span="8">
          <el-card shadow="hover" class="feature-card" @click="$router.push('/documents')">
            <div class="feature-icon">📄</div>
            <h3>文献管理</h3>
            <p>上传 PDF 文献，自动解析分块并向量化存储</p>
            <div class="stats" v-if="stats.documentCount !== undefined">
              <el-statistic title="已上传文献" :value="stats.documentCount" />
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" class="feature-card" @click="$router.push('/chat')">
            <div class="feature-icon">🤖</div>
            <h3>智能问答</h3>
            <p>基于 RAG 的智能问答，引用原文回答您的问题</p>
            <div class="stats" v-if="stats.conversationCount !== undefined">
              <el-statistic title="会话数" :value="stats.conversationCount" />
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" class="feature-card" @click="$router.push('/documents')">
            <div class="feature-icon">🔧</div>
            <h3>智能工具</h3>
            <p>翻译、摘要解读等辅助工具，助力科研</p>
            <div class="stats">
              <el-statistic title="可用工具" :value="2" />
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { documentAPI, chatAPI } from '../api'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const activeMenu = computed(() => route.path)
const stats = ref({})

const handleCommand = (command) => {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}

onMounted(async () => {
  try {
    const [docsRes, chatsRes] = await Promise.all([
      documentAPI.getList({ page: 1, per_page: 1 }),
      chatAPI.getConversations(),
    ])
    stats.value = {
      documentCount: docsRes.total || 0,
      conversationCount: chatsRes.conversations?.length || 0,
    }
  } catch (err) {
    // 忽略首页统计加载错误
  }
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

.header-left {
  display: flex;
  align-items: center;
}

.logo {
  font-size: 20px;
  color: #409eff;
  white-space: nowrap;
  margin-right: 40px;
}

.nav-menu {
  flex: 1;
  border-bottom: none;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  gap: 8px;
}

.username {
  font-size: 14px;
  color: #606266;
}

.main-content {
  flex: 1;
  padding: 40px;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.welcome-section {
  text-align: center;
  margin-bottom: 48px;
}

.welcome-section h1 {
  font-size: 32px;
  color: #303133;
  margin-bottom: 12px;
}

.welcome-section p {
  font-size: 16px;
  color: #909399;
}

.feature-card {
  text-align: center;
  cursor: pointer;
  transition: transform 0.3s;
  height: 100%;
}

.feature-card:hover {
  transform: translateY(-4px);
}

.feature-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.feature-card h3 {
  font-size: 18px;
  color: #303133;
  margin-bottom: 8px;
}

.feature-card p {
  font-size: 14px;
  color: #909399;
  margin-bottom: 16px;
}

.stats {
  margin-top: 12px;
}
</style>
