<template>
  <el-card shadow="hover" class="document-card">
    <div class="card-header">
      <h4 class="doc-title" :title="document.title">{{ document.title }}</h4>
      <el-tag :type="statusType" size="small">{{ statusText }}</el-tag>
    </div>

    <div class="card-meta">
      <div class="meta-item" v-if="document.authors">
        <el-icon><User /></el-icon>
        <span>{{ document.authors }}</span>
      </div>
      <div class="meta-item">
        <el-icon><Clock /></el-icon>
        <span>{{ formatDate(document.upload_time) }}</span>
      </div>
      <div class="meta-item" v-if="document.chunk_count > 0">
        <el-icon><Document /></el-icon>
        <span>{{ document.chunk_count }} 个分块</span>
      </div>
    </div>

    <div class="card-actions">
      <el-button size="small" @click="$emit('view', document)">详情</el-button>
      <el-button size="small" type="success" @click="$emit('summarize', document)" :disabled="document.status !== 'ready'">
        解读
      </el-button>
      <el-button size="small" type="danger" @click="$emit('delete', document)">删除</el-button>
    </div>

    <!-- 处理中进度条 -->
    <el-progress
      v-if="document.status === 'processing'"
      :percentage="50"
      :indeterminate="true"
      :stroke-width="3"
      class="processing-bar"
    />
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  document: { type: Object, required: true },
})

defineEmits(['view', 'summarize', 'delete'])

const statusType = computed(() => {
  const map = { pending: 'info', processing: '', ready: 'success', failed: 'danger' }
  return map[props.document.status] || 'info'
})

const statusText = computed(() => {
  const map = { pending: '待处理', processing: '处理中', ready: '已就绪', failed: '失败' }
  return map[props.document.status] || props.document.status
})

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}
</script>

<style scoped>
.document-card {
  transition: transform 0.2s;
}

.document-card:hover {
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  gap: 8px;
}

.doc-title {
  font-size: 15px;
  color: #303133;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  flex: 1;
}

.card-meta {
  margin-bottom: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #909399;
  margin-bottom: 4px;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.processing-bar {
  margin-top: 8px;
}
</style>
