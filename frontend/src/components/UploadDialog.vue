<template>
  <el-dialog
    v-model="visible"
    title="上传文献"
    width="500px"
    :close-on-click-modal="!processing"
    :close-on-press-escape="!processing"
    :show-close="!processing"
    @close="resetForm"
  >
    <!-- 上传表单 -->
    <div v-if="!processing">
      <el-form :model="form" label-width="80px">
        <el-form-item label="PDF 文件" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".pdf"
            :on-change="handleFileChange"
            :on-exceed="handleExceed"
            drag
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              将 PDF 文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">仅支持 PDF 格式，文件大小不超过 50MB</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="文献标题">
          <el-input v-model="form.title" placeholder="可选，留空将自动从 PDF 中提取" />
        </el-form-item>
        <el-form-item label="作者">
          <el-input v-model="form.authors" placeholder="可选" />
        </el-form-item>
      </el-form>
    </div>

    <!-- 处理进度 -->
    <div v-else class="progress-area">
      <div class="progress-icon">
        <el-icon v-if="progressStatus === 'success'" :size="48" color="#67c23a"><CircleCheck /></el-icon>
        <el-icon v-else-if="progressStatus === 'exception'" :size="48" color="#f56c6c"><CircleClose /></el-icon>
        <el-icon v-else class="is-loading" :size="48" color="#409eff"><Loading /></el-icon>
      </div>
      <div class="progress-title">
        {{ progressStatus === 'success' ? '处理完成' : progressStatus === 'exception' ? '处理失败' : '正在处理文献…' }}
      </div>
      <el-progress
        :percentage="currentProgress"
        :status="progressStatus || undefined"
        :stroke-width="10"
        class="progress-bar"
      />
      <div class="progress-step">{{ stepMessage }}</div>
    </div>

    <template #footer>
      <!-- 表单底部 -->
      <div v-if="!processing">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!selectedFile" @click="handleUpload">
          上传
        </el-button>
      </div>
      <!-- 进度底部 -->
      <div v-else>
        <el-button v-if="progressStatus === 'exception'" @click="resetForm">关闭</el-button>
        <el-button v-if="progressStatus === 'success'" type="primary" @click="resetForm">完成</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { documentAPI } from '../api'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'uploaded'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const uploadRef = ref()
const uploading = ref(false)
const selectedFile = ref(null)
const form = ref({ title: '', authors: '' })

// 处理进度状态
const processing = ref(false)
const currentProgress = ref(0)
const stepMessage = ref('')
const progressStatus = ref('')   // '' | 'success' | 'exception'

let pollTimer = null

const handleFileChange = (file) => {
  if (file.raw.type !== 'application/pdf') {
    ElMessage.error('仅支持 PDF 格式文件')
    uploadRef.value?.clearFiles()
    selectedFile.value = null
    return
  }
  if (file.raw.size > 50 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 50MB')
    uploadRef.value?.clearFiles()
    selectedFile.value = null
    return
  }
  selectedFile.value = file.raw
}

const handleExceed = () => {
  ElMessage.warning('只能上传一个文件')
}

const handleUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.error('请选择 PDF 文件')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    if (form.value.title) formData.append('title', form.value.title)
    if (form.value.authors) formData.append('authors', form.value.authors)

    const data = await documentAPI.upload(formData)
    // 进入进度轮询阶段
    processing.value = true
    currentProgress.value = 2
    stepMessage.value = '文件已上传，等待处理…'
    startPolling(data.document_id)
    emit('uploaded', data.document_id)
  } catch {
    // 错误已在拦截器处理
  } finally {
    uploading.value = false
  }
}

const startPolling = (docId) => {
  pollTimer = setInterval(async () => {
    try {
      const data = await documentAPI.getStatus(docId)

      if (data.status === 'ready') {
        currentProgress.value = 100
        stepMessage.value = `处理完成，共 ${data.chunk_count} 个分块`
        progressStatus.value = 'success'
        stopPolling()
      } else if (data.status === 'failed') {
        currentProgress.value = currentProgress.value
        stepMessage.value = data.message || '处理失败，请重试'
        progressStatus.value = 'exception'
        stopPolling()
      } else {
        // pending / processing
        const p = data.progress || 0
        if (p > currentProgress.value) {
          currentProgress.value = p
        }
        if (data.status_message) {
          stepMessage.value = data.status_message
        }
      }
    } catch {
      // 网络抖动，继续轮询
    }
  }, 1500)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const resetForm = () => {
  stopPolling()
  processing.value = false
  currentProgress.value = 0
  stepMessage.value = ''
  progressStatus.value = ''
  form.value = { title: '', authors: '' }
  selectedFile.value = null
  uploadRef.value?.clearFiles()
  visible.value = false
}
</script>

<style scoped>
:deep(.el-upload-dragger) { width: 100%; }
:deep(.el-upload) { width: 100%; }
:deep(.el-upload-list) { max-width: 100%; }
:deep(.el-upload-list__item-name) {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 16px 0 8px;
}

.progress-icon {
  line-height: 1;
}

.progress-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.progress-bar {
  width: 100%;
}

.progress-step {
  font-size: 13px;
  color: #909399;
  min-height: 20px;
  text-align: center;
}
</style>
