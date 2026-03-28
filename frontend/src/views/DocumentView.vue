<template>
  <div class="layout">
    <!-- 顶部导航栏 -->
    <el-header class="header">
      <div class="header-left">
        <h2 class="logo" @click="$router.push('/home')" style="cursor:pointer">📚 PaperPilot</h2>
      </div>
      <el-menu mode="horizontal" default-active="/documents" router class="nav-menu">
        <el-menu-item index="/home"><el-icon><HomeFilled /></el-icon>首页</el-menu-item>
        <el-menu-item index="/documents"><el-icon><Document /></el-icon>文献管理</el-menu-item>
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
      <!-- 工具栏 -->
      <div class="toolbar">
        <el-input v-model="searchKeyword" placeholder="搜索文献标题/作者" prefix-icon="Search" clearable style="width: 300px" @input="handleSearch" />
        <div class="toolbar-right">
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button value="card"><el-icon><Grid /></el-icon></el-radio-button>
            <el-radio-button value="table"><el-icon><List /></el-icon></el-radio-button>
          </el-radio-group>
          <el-button type="primary" icon="Upload" @click="showUploadDialog = true">上传文献</el-button>
        </div>
      </div>

      <!-- 卡片视图 -->
      <div v-if="viewMode === 'card'" class="card-grid">
        <document-card
          v-for="doc in documents"
          :key="doc.id"
          :document="doc"
          @view="handleView"
          @summarize="handleSummarize"
          @delete="handleDelete"
          @preview="openPreview"
        />
        <el-empty v-if="documents.length === 0" description="暂无文献，点击上方按钮上传" />
      </div>

      <!-- 表格视图 -->
      <el-table v-if="viewMode === 'table'" :data="documents" stripe style="width: 100%">
        <el-table-column prop="title" label="标题" min-width="250" show-overflow-tooltip />
        <el-table-column prop="authors" label="作者" width="180" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块数" width="80" align="center" />
        <el-table-column label="上传时间" width="170">
          <template #default="{ row }">{{ formatDate(row.upload_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="openPreview(row)" :disabled="row.status !== 'ready'">浏览</el-button>
            <el-button size="small" @click="handleView(row)">详情</el-button>
            <el-button size="small" type="success" @click="handleSummarize(row)" :disabled="row.status !== 'ready'">解读</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination" v-if="total > 0">
        <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next" @size-change="fetchDocuments" @current-change="fetchDocuments" />
      </div>
    </el-main>

    <!-- 上传对话框 -->
    <upload-dialog v-model="showUploadDialog" @uploaded="onUploaded" />

    <!-- 文献详情抽屉 -->
    <el-drawer v-model="showDetail" :title="detailDoc?.title" size="500px">
      <template v-if="detailDoc">
        <!-- 显示模式 -->
        <div v-if="!isEditingDetail">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="上传者">{{ detailDoc.uploader }}</el-descriptions-item>
            <el-descriptions-item label="作者">{{ detailDoc.authors || '未知' }}</el-descriptions-item>
            <el-descriptions-item label="DOI" v-if="detailDoc.doi">
              <a :href="`https://doi.org/${detailDoc.doi}`" target="_blank" rel="noopener">{{ detailDoc.doi }}</a>
            </el-descriptions-item>
            <el-descriptions-item label="语言">{{ detailDoc.language }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusType(detailDoc.status)">{{ statusText(detailDoc.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="分块数">{{ detailDoc.chunk_count }}</el-descriptions-item>
            <el-descriptions-item label="文件大小">{{ formatSize(detailDoc.file_size) }}</el-descriptions-item>
            <el-descriptions-item label="上传时间">{{ formatDate(detailDoc.upload_time) }}</el-descriptions-item>
          </el-descriptions>

          <div v-if="detailDoc.abstract" class="abstract-section">
            <h4>摘要</h4>
            <p>{{ detailDoc.abstract }}</p>
          </div>

          <el-button type="primary" style="margin-top: 16px; width: 100%" @click="openPreview(detailDoc)" :disabled="detailDoc.status !== 'ready'">📄 浏览原文</el-button>
          <el-button style="margin-top: 8px; width: 100%" @click="startEditing">✏️ 编辑信息</el-button>

          <tool-panel :document="detailDoc" class="tool-section" />
        </div>

        <!-- 编辑模式 -->
        <div v-if="isEditingDetail">
          <el-form :model="editingDoc" label-width="80px">
            <el-form-item label="标题" required>
              <el-input v-model="editingDoc.title" placeholder="论文标题" />
            </el-form-item>
            <el-form-item label="作者">
              <el-input
                v-model="editingDoc.authors"
                type="textarea"
                :rows="3"
                placeholder="多个作者用分号分隔，例如: 作者1; 作者2; 作者3"
              />
            </el-form-item>
            <el-form-item label="DOI">
              <el-input v-model="editingDoc.doi" placeholder="例如: 10.1234/example" />
            </el-form-item>
          </el-form>

          <div style="display: flex; gap: 8px; margin-top: 16px">
            <el-button type="primary" @click="saveEditing" :loading="savingDetail">保存</el-button>
            <el-button @click="cancelEditing">取消</el-button>
          </div>
        </div>
      </template>
    </el-drawer>

    <!-- PDF 预览 -->
    <pdf-viewer v-model="showPdfViewer" :doc-id="previewDocId" :doc-title="previewDocTitle" />
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { documentAPI } from '../api'
import UploadDialog from '../components/UploadDialog.vue'
import DocumentCard from '../components/DocumentCard.vue'
import ToolPanel from '../components/ToolPanel.vue'
import PdfViewer from '../components/PdfViewer.vue'

const router = useRouter()
const authStore = useAuthStore()

const documents = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const searchKeyword = ref('')
const viewMode = ref('card')
const showUploadDialog = ref(false)
const showDetail = ref(false)
const detailDoc = ref(null)
const isEditingDetail = ref(false)
const editingDoc = ref(null)
const savingDetail = ref(false)
const showPdfViewer = ref(false)
const previewDocId = ref(null)
const previewDocTitle = ref('')

// 状态轮询 timer map
const pollingTimers = ref({})

const handleCommand = (command) => {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}

const statusType = (status) => {
  const map = { pending: 'info', processing: '', ready: 'success', failed: 'danger' }
  return map[status] || 'info'
}

const statusText = (status) => {
  const map = { pending: '待处理', processing: '处理中', ready: '已就绪', failed: '失败' }
  return map[status] || status
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatSize = (bytes) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let idx = 0
  let size = bytes
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024
    idx++
  }
  return `${size.toFixed(1)} ${units[idx]}`
}

let searchTimer = null
const handleSearch = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    fetchDocuments()
  }, 300)
}

const fetchDocuments = async () => {
  try {
    const data = await documentAPI.getList({
      page: currentPage.value,
      per_page: pageSize.value,
      search: searchKeyword.value,
    })
    documents.value = data.documents || []
    total.value = data.total || 0

    // 对处理中的文献启动轮询
    documents.value.forEach((doc) => {
      if ((doc.status === 'pending' || doc.status === 'processing') && !pollingTimers.value[doc.id]) {
        startPolling(doc.id)
      }
    })
  } catch (err) {
    // 错误已在拦截器处理
  }
}

const startPolling = (docId) => {
  const timer = setInterval(async () => {
    try {
      const data = await documentAPI.getStatus(docId)
      const idx = documents.value.findIndex((d) => d.id === docId)
      if (idx !== -1) {
        documents.value[idx].status = data.status
        documents.value[idx].chunk_count = data.chunk_count
      }
      if (data.status === 'ready' || data.status === 'failed') {
        clearInterval(pollingTimers.value[docId])
        delete pollingTimers.value[docId]
        // 重新拉取列表，刷新标题、作者、DOI 等提取结果
        fetchDocuments()
        if (data.status === 'ready') {
          ElMessage.success(`文献处理完成，共 ${data.chunk_count} 个分块`)
        } else {
          ElMessage.error(`文献处理失败: ${data.message}`)
        }
      }
    } catch (err) {
      clearInterval(pollingTimers.value[docId])
      delete pollingTimers.value[docId]
    }
  }, 3000)
  pollingTimers.value[docId] = timer
}

const onUploaded = () => {
  showUploadDialog.value = false
  fetchDocuments()
}

const handleView = (doc) => {
  detailDoc.value = doc
  showDetail.value = true
}

const openPreview = (doc) => {
  previewDocId.value = doc.id
  previewDocTitle.value = doc.title
  showPdfViewer.value = true
}

const handleSummarize = (doc) => {
  detailDoc.value = doc
  showDetail.value = true
}

const startEditing = () => {
  editingDoc.value = {
    title: detailDoc.value.title,
    authors: detailDoc.value.authors,
    doi: detailDoc.value.doi,
  }
  isEditingDetail.value = true
}

const cancelEditing = () => {
  isEditingDetail.value = false
  editingDoc.value = null
}

const saveEditing = async () => {
  if (!editingDoc.value.title.trim()) {
    ElMessage.error('标题不能为空')
    return
  }

  savingDetail.value = true
  try {
    await documentAPI.update(detailDoc.value.id, {
      title: editingDoc.value.title.trim(),
      authors: editingDoc.value.authors.trim(),
      doi: editingDoc.value.doi.trim(),
    })
    ElMessage.success('文献信息已更新')
    isEditingDetail.value = false
    // 刷新详情和列表
    const updated = await documentAPI.get(detailDoc.value.id)
    detailDoc.value = updated
    fetchDocuments()
  } catch (err) {
    // 错误已在拦截器处理
  } finally {
    savingDetail.value = false
  }
}

const handleDelete = async (doc) => {
  try {
    await ElMessageBox.confirm(`确定要删除文献「${doc.title}」吗？`, '提示', {
      type: 'warning',
    })
    await documentAPI.delete(doc.id)
    ElMessage.success('删除成功')
    fetchDocuments()
  } catch (err) {
    // 取消删除或错误已处理
  }
}

onMounted(() => {
  fetchDocuments()
})

// 清理轮询
onBeforeUnmount(() => {
  Object.values(pollingTimers.value).forEach(clearInterval)
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
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.toolbar-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

.abstract-section {
  margin-top: 20px;
}

.abstract-section h4 {
  margin-bottom: 8px;
  color: #303133;
}

.abstract-section p {
  color: #606266;
  line-height: 1.6;
  font-size: 14px;
}

.tool-section {
  margin-top: 20px;
}
</style>
