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
        <el-menu-item index="/library">
          <el-icon><Collection /></el-icon>文献库
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

      <!-- 文献搜索区域 -->
      <div class="search-section">
        <h2 class="section-title">🔍 搜索文献</h2>
        <div class="search-bar">
          <el-input
            v-model="searchKeyword"
            placeholder="输入文献标题、作者关键词..."
            size="large"
            clearable
            @keyup.enter="doSearch"
            @clear="clearSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" size="large" @click="doSearch" :loading="searching">
            搜索
          </el-button>
        </div>

        <!-- 搜索结果 -->
        <div v-if="searchPerformed" class="search-results">
          <div class="results-header">
            <span class="results-count">找到 <strong>{{ searchResults.length }}</strong> 篇相关文献</span>
            <el-button v-if="searchResults.length > 0" text type="primary" @click="clearSearch">清除搜索</el-button>
          </div>

          <el-empty v-if="searchResults.length === 0" description="未找到匹配的文献，试试其他关键词？">
            <el-button type="primary" @click="$router.push('/documents')">去上传文献</el-button>
          </el-empty>

          <div v-else class="results-list">
            <el-card v-for="doc in searchResults" :key="doc.id" class="result-card" shadow="hover">
              <div class="result-content">
                <div class="result-main">
                  <h4 class="result-title" v-html="highlightKeyword(doc.title)"></h4>
                  <div class="result-meta">
                    <span v-if="doc.authors" class="meta-item">
                      <el-icon><User /></el-icon>
                      <span v-html="highlightKeyword(doc.authors)"></span>
                    </span>
                    <span class="meta-item">
                      <el-icon><Calendar /></el-icon>
                      {{ formatDate(doc.upload_time) }}
                    </span>
                    <el-tag :type="statusType(doc.status)" size="small">{{ statusText(doc.status) }}</el-tag>
                    <span v-if="doc.chunk_count" class="meta-item">{{ doc.chunk_count }} 个分块</span>
                  </div>
                  <p v-if="doc.abstract" class="result-abstract">{{ doc.abstract.slice(0, 200) }}{{ doc.abstract.length > 200 ? '...' : '' }}</p>
                </div>
                <div class="result-actions">
                  <el-button size="small" type="primary" plain @click="openPreview(doc)">
                    <el-icon><View /></el-icon> 浏览
                  </el-button>
                  <el-button size="small" plain @click="goChat(doc)">
                    <el-icon><ChatDotRound /></el-icon> 提问
                  </el-button>
                </div>
              </div>
            </el-card>
          </div>
        </div>
      </div>
    </el-main>

    <!-- PDF 预览 -->
    <pdf-viewer v-model="showPdfViewer" :doc-id="previewDocId" :doc-title="previewDocTitle" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { documentAPI, chatAPI } from '../api'
import PdfViewer from '../components/PdfViewer.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const activeMenu = computed(() => route.path)
const stats = ref({})

// 搜索相关
const searchKeyword = ref('')
const searchResults = ref([])
const searchPerformed = ref(false)
const searching = ref(false)

// PDF 预览
const showPdfViewer = ref(false)
const previewDocId = ref(null)
const previewDocTitle = ref('')

const handleCommand = (command) => {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}

const doSearch = async () => {
  const keyword = searchKeyword.value.trim()
  if (!keyword) return
  searching.value = true
  searchPerformed.value = true
  try {
    const data = await documentAPI.getList({ page: 1, per_page: 50, search: keyword })
    searchResults.value = data.documents || []
  } catch (err) {
    searchResults.value = []
  } finally {
    searching.value = false
  }
}

const clearSearch = () => {
  searchKeyword.value = ''
  searchResults.value = []
  searchPerformed.value = false
}

const highlightKeyword = (text) => {
  if (!text || !searchKeyword.value.trim()) return text || ''
  const kw = searchKeyword.value.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return text.replace(new RegExp(`(${kw})`, 'gi'), '<mark>$1</mark>')
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const statusType = (status) => {
  const map = { pending: 'info', processing: '', ready: 'success', failed: 'danger' }
  return map[status] || 'info'
}

const statusText = (status) => {
  const map = { pending: '待处理', processing: '处理中', ready: '已就绪', failed: '失败' }
  return map[status] || status
}

const openPreview = (doc) => {
  previewDocId.value = doc.id
  previewDocTitle.value = doc.title
  showPdfViewer.value = true
}

const goChat = (doc) => {
  router.push({ path: '/chat', query: { doc_id: doc.id } })
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

/* 搜索区域 */
.search-section {
  margin-top: 48px;
}

.section-title {
  font-size: 20px;
  color: #303133;
  margin-bottom: 20px;
}

.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.search-bar .el-input {
  flex: 1;
}

.search-results {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.results-count {
  font-size: 14px;
  color: #909399;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-card {
  cursor: default;
  transition: box-shadow 0.2s;
}

.result-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.result-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.result-main {
  flex: 1;
  min-width: 0;
}

.result-title {
  font-size: 16px;
  color: #303133;
  margin: 0 0 8px 0;
  line-height: 1.4;
}

.result-title :deep(mark) {
  background: #ffd54f;
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
}

.result-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #909399;
}

.meta-item :deep(mark) {
  background: #ffd54f;
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
}

.result-abstract {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  margin: 0;
}

.result-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}
</style>
