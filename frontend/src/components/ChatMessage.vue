<template>
  <div :class="['chat-message', message.role]">
    <div class="avatar">
      {{ message.role === 'user' ? '👤' : '🤖' }}
    </div>
    <div class="message-body">
      <div class="message-content" v-html="renderedContent"></div>

      <!-- 引用来源 -->
      <div v-if="message.sources && message.sources.length > 0" class="sources-section">
        <el-collapse>
          <el-collapse-item>
            <template #title>
              <el-icon><Document /></el-icon>
              <span style="margin-left:4px">引用来源（{{ message.sources.length }} 条）</span>
            </template>
            <div v-for="(source, idx) in message.sources" :key="idx" class="source-item">
              <div class="source-header">
                <el-tag size="small" type="info">[{{ idx + 1 }}]</el-tag>
                <span class="source-title source-link" @click="handlePreviewSource(source)">{{ source.doc_title || '未知文献' }}</span>
                <el-tag size="small" v-if="source.page_number">第{{ source.page_number }}页</el-tag>
                <el-tag size="small" type="success" v-if="source.score">
                  相似度 {{ (source.score * 100).toFixed(1) }}%
                </el-tag>
              </div>
              <div class="source-content">{{ source.content_preview }}</div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['preview-doc'])

const handlePreviewSource = (source) => {
  if (source.doc_id) {
    emit('preview-doc', {
      docId: source.doc_id,
      docTitle: source.doc_title || '文献预览',
      page: source.page_number || 0,
    })
  }
}

// Markdown 渲染，并高亮引用编号 [1] [2] 等
const renderedContent = computed(() => {
  if (!props.message.content) return ''

  let html = marked.parse(props.message.content)

  // 高亮引用标记 [数字]
  html = html.replace(
    /\[(\d+)\]/g,
    '<span class="citation-mark">[$1]</span>'
  )

  return html
})
</script>

<style scoped>
.chat-message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 85%;
}

.chat-message.user {
  flex-direction: row-reverse;
  margin-left: auto;
}

.chat-message.assistant {
  margin-right: auto;
}

.avatar {
  font-size: 28px;
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.message-body {
  flex: 1;
  min-width: 0;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}

.user .message-content {
  background: #409eff;
  color: white;
  border-bottom-right-radius: 4px;
}

.assistant .message-content {
  background: #f4f4f5;
  color: #303133;
  border-bottom-left-radius: 4px;
}

.message-content :deep(p) {
  margin: 0 0 8px 0;
}

.message-content :deep(p:last-child) {
  margin-bottom: 0;
}

.message-content :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.message-content :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}

.message-content :deep(pre code) {
  background: none;
  padding: 0;
}

.message-content :deep(.citation-mark) {
  color: #409eff;
  font-weight: bold;
  cursor: pointer;
}

.user .message-content :deep(.citation-mark) {
  color: #a0cfff;
}

/* 引用来源 */
.sources-section {
  margin-top: 8px;
}

.sources-section :deep(.el-collapse-item__header) {
  font-size: 13px;
  color: #909399;
  height: 36px;
}

.source-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.source-item:last-child {
  border-bottom: none;
}

.source-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.source-title {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.source-link {
  cursor: pointer;
  color: #409eff;
}

.source-link:hover {
  text-decoration: underline;
}

.source-content {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 4px;
}
</style>
