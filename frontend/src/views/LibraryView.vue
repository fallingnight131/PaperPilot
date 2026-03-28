<template>
  <div class="layout">
    <!-- 顶部导航栏 -->
    <el-header class="header">
      <div class="header-left">
        <h2 class="logo" @click="$router.push('/home')" style="cursor:pointer">📚 PaperPilot</h2>
      </div>
      <el-menu mode="horizontal" default-active="/library" router class="nav-menu">
        <el-menu-item index="/home"><el-icon><HomeFilled /></el-icon>首页</el-menu-item>
        <el-menu-item index="/documents"><el-icon><Document /></el-icon>文献管理</el-menu-item>
        <el-menu-item index="/library"><el-icon><Collection /></el-icon>文献库</el-menu-item>
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
      <div class="toolbar">
        <div class="toolbar-title">
          <h3>文献库</h3>
          <span class="total-tip">共 {{ total }} 篇已就绪文献</span>
        </div>
        <div class="search-group">
          <el-input
            v-model="searchKeyword"
            placeholder="标题 / 作者 / DOI"
            prefix-icon="Search"
            clearable
            style="width: 240px"
            @input="handleSearch"
          />
          <el-input
            v-model="uploaderKeyword"
            placeholder="上传者"
            prefix-icon="User"
            clearable
            style="width: 150px"
            @input="handleSearch"
          />
        </div>
      </div>

      <el-table :data="documents" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="title" label="标题" min-width="260" show-overflow-tooltip />
        <el-table-column prop="authors" label="作者" width="200" show-overflow-tooltip />
        <el-table-column label="DOI" width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <a v-if="row.doi" :href="`https://doi.org/${row.doi}`" target="_blank" rel="noopener" class="doi-link">
              {{ row.doi }}
            </a>
            <span v-else class="empty-cell">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="uploader" label="上传者" width="100" />
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">{{ formatDate(row.upload_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="openPreview(row)">浏览</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination" v-if="total > 0">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchLibrary"
          @current-change="fetchLibrary"
        />
      </div>

      <el-empty v-if="!loading && documents.length === 0" description="文献库暂无文献" />
    </el-main>

    <pdf-viewer v-model="showPdfViewer" :doc-id="previewDocId" :doc-title="previewDocTitle" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { documentAPI } from '../api'
import PdfViewer from '../components/PdfViewer.vue'

const router = useRouter()
const authStore = useAuthStore()

const documents = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const uploaderKeyword = ref('')
const loading = ref(false)
const showPdfViewer = ref(false)
const previewDocId = ref(null)
const previewDocTitle = ref('')

const handleCommand = (command) => {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}

const fetchLibrary = async () => {
  loading.value = true
  try {
    const data = await documentAPI.getLibrary({
      page: currentPage.value,
      per_page: pageSize.value,
      search: searchKeyword.value,
      uploader: uploaderKeyword.value,
    })
    documents.value = data.documents || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

let searchTimer = null
const handleSearch = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    fetchLibrary()
  }, 300)
}

const openPreview = (doc) => {
  previewDocId.value = doc.id
  previewDocTitle.value = doc.title
  showPdfViewer.value = true
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(fetchLibrary)
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
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.toolbar-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.toolbar-title h3 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.total-tip {
  font-size: 13px;
  color: #909399;
}

.search-group {
  display: flex;
  gap: 8px;
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

.doi-link {
  color: #409eff;
  text-decoration: none;
  font-size: 12px;
}

.doi-link:hover {
  text-decoration: underline;
}

.empty-cell {
  color: #c0c4cc;
}
</style>
