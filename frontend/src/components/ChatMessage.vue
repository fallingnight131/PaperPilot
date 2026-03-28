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

      <!-- 复制按钮：气泡和引用来源下方 -->
      <div class="copy-row">
        <el-tooltip content="复制" placement="top" :show-after="300">
          <button class="copy-btn" @click="copyContent">
            <el-icon v-if="copied"><Select /></el-icon>
            <el-icon v-else><CopyDocument /></el-icon>
          </button>
        </el-tooltip>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import katex from 'katex'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['preview-doc'])

const copied = ref(false)

const copyContent = async () => {
  try {
    await navigator.clipboard.writeText(props.message.content || '')
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // 降级方案
    const el = document.createElement('textarea')
    el.value = props.message.content || ''
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}

const handlePreviewSource = (source) => {
  if (source.doc_id) {
    emit('preview-doc', {
      docId: source.doc_id,
      docTitle: source.doc_title || '文献预览',
      page: source.page_number || 0,
    })
  }
}

// Markdown + KaTeX 渲染
const renderedContent = computed(() => {
  if (!props.message.content) return ''

  const blocks = [] // { math, display }

  // Step 1：先把数学公式替换成占位符，防止 marked 把 _ 解析成斜体
  let text = props.message.content
    // 行间公式 $$...$$
    .replace(/\$\$([\s\S]+?)\$\$/g, (_, math) => {
      blocks.push({ math: math.trim(), display: true })
      return `@@MATH_${blocks.length - 1}@@`
    })
    // 行内公式 $...$（单行，长度限制避免误匹配）
    .replace(/\$([^\n$]{1,400}?)\$/g, (_, math) => {
      blocks.push({ math: math.trim(), display: false })
      return `@@MATH_${blocks.length - 1}@@`
    })

  // Step 2：marked 处理 Markdown
  let html = marked.parse(text)

  // Step 3：把占位符还原为 KaTeX 渲染结果
  html = html.replace(/@@MATH_(\d+)@@/g, (_, i) => {
    const { math, display } = blocks[Number(i)]
    try {
      return katex.renderToString(math, { displayMode: display, throwOnError: false })
    } catch {
      return display ? `$$${math}$$` : `$${math}$`
    }
  })

  // Step 4：高亮引用标记 [数字]
  html = html.replace(/\[(\d+)\]/g, '<span class="citation-mark">[$1]</span>')

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
  display: flex;
  flex-direction: column;
}

.copy-row {
  display: flex;
  margin-top: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.assistant .copy-row {
  justify-content: flex-start;
}

.user .copy-row {
  justify-content: flex-end;
}

.message-body:hover .copy-row {
  opacity: 1;
}

.copy-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 4px;
  color: #c0c4cc;
  font-size: 13px;
  line-height: 1;
  display: flex;
  align-items: center;
}

.copy-btn:hover {
  color: #409eff;
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
