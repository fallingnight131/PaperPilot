<template>
  <el-dialog v-model="visible" title="上传文献" width="500px" @close="resetForm">
    <el-form ref="formRef" :model="form" label-width="80px">
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

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="uploading" :disabled="!selectedFile" @click="handleUpload">
        上传
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { documentAPI } from '../api'

const props = defineProps({
  modelValue: Boolean,
})
const emit = defineEmits(['update:modelValue', 'uploaded'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const formRef = ref()
const uploadRef = ref()
const uploading = ref(false)
const selectedFile = ref(null)

const form = ref({
  title: '',
  authors: '',
})

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
    ElMessage.success('文献上传成功，正在处理中')
    emit('uploaded', data.document_id)
    resetForm()
  } catch (err) {
    // 错误已在拦截器处理
  } finally {
    uploading.value = false
  }
}

const resetForm = () => {
  form.value = { title: '', authors: '' }
  selectedFile.value = null
  uploadRef.value?.clearFiles()
}
</script>

<style scoped>
:deep(.el-upload-dragger) {
  width: 100%;
}

:deep(.el-upload) {
  width: 100%;
}

:deep(.el-upload-list) {
  max-width: 100%;
}

:deep(.el-upload-list__item-name) {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
