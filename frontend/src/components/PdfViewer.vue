<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="90%"
    top="2vh"
    :close-on-click-modal="false"
    class="pdf-viewer-dialog"
    @close="handleClose"
  >
    <div class="pdf-toolbar">
      <span class="pdf-filename">{{ title }}</span>
      <div class="pdf-actions">
        <el-button size="small" @click="openInNewTab" icon="TopRight">新窗口打开</el-button>
        <el-button size="small" @click="downloadPdf" icon="Download">下载</el-button>
      </div>
    </div>
    <div class="pdf-container">
      <iframe
        v-if="pdfUrl"
        :src="pdfUrl"
        class="pdf-iframe"
        frameborder="0"
      />
      <div v-else class="pdf-loading">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  docId: { type: Number, default: null },
  docTitle: { type: String, default: '文献预览' },
  page: { type: Number, default: 0 },
})

const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const title = computed(() => props.docTitle || '文献预览')

const pdfUrl = ref('')

watch(() => [props.modelValue, props.docId], ([show, docId]) => {
  if (show && docId) {
    const token = localStorage.getItem('token')
    // 构造带 token 的 preview URL，通过 page 参数跳转页码
    const pageFragment = props.page > 0 ? `#page=${props.page}` : ''
    pdfUrl.value = `/api/documents/${docId}/preview?token=${encodeURIComponent(token)}${pageFragment}`
  } else {
    pdfUrl.value = ''
  }
}, { immediate: true })

const handleClose = () => {
  visible.value = false
}

const openInNewTab = () => {
  if (pdfUrl.value) {
    window.open(pdfUrl.value, '_blank')
  }
}

const downloadPdf = () => {
  if (!pdfUrl.value) return
  const a = document.createElement('a')
  a.href = pdfUrl.value
  a.download = props.docTitle || 'document.pdf'
  a.click()
}
</script>

<style scoped>
.pdf-viewer-dialog :deep(.el-dialog) {
  margin-top: 2vh !important;
  margin-bottom: 2vh !important;
}

.pdf-viewer-dialog :deep(.el-dialog__body) {
  padding: 0;
  height: calc(96vh - 54px);
}

.pdf-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.pdf-filename {
  font-size: 14px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 12px;
}

.pdf-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.pdf-container {
  height: calc(96vh - 54px - 42px - 20px);
  overflow: hidden;
}

.pdf-iframe {
  width: 100%;
  height: 100%;
  border: none;
}

.pdf-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: #909399;
}
</style>
