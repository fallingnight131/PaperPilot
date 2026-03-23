<template>
  <div class="tool-panel">
    <el-tabs v-model="activeTab">
      <!-- 翻译工具 -->
      <el-tab-pane label="翻译" name="translate">
        <el-form label-position="top">
          <el-form-item label="翻译文本">
            <el-input v-model="translateInput" type="textarea" :rows="4" placeholder="输入要翻译的文本..." />
          </el-form-item>
          <el-form-item label="目标语言">
            <el-select v-model="targetLanguage" style="width: 100%">
              <el-option label="中文" value="中文" />
              <el-option label="English" value="English" />
              <el-option label="日本語" value="日本語" />
              <el-option label="한국어" value="한국어" />
            </el-select>
          </el-form-item>
          <el-button type="primary" :loading="translateLoading" @click="handleTranslate" :disabled="!translateInput.trim()">
            翻译
          </el-button>
        </el-form>

        <div v-if="translateResult" class="result-box">
          <h4>翻译结果</h4>
          <p>{{ translateResult }}</p>
        </div>
      </el-tab-pane>

      <!-- 摘要解读 -->
      <el-tab-pane label="摘要解读" name="summarize">
        <div v-if="document">
          <p class="hint">对文献「{{ document.title }}」生成结构化解读</p>
          <el-button type="primary" :loading="summarizeLoading" @click="handleSummarize" :disabled="document.status !== 'ready'">
            生成解读
          </el-button>
        </div>
        <div v-else>
          <el-form label-position="top">
            <el-form-item label="输入文本">
              <el-input v-model="summarizeInput" type="textarea" :rows="6" placeholder="粘贴需要解读的文本..." />
            </el-form-item>
            <el-button type="primary" :loading="summarizeLoading" @click="handleSummarizeText" :disabled="!summarizeInput.trim()">
              生成解读
            </el-button>
          </el-form>
        </div>

        <div v-if="summaryResult" class="result-box">
          <h4>结构化解读</h4>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="研究背景">{{ summaryResult.background }}</el-descriptions-item>
            <el-descriptions-item label="研究方法">{{ summaryResult.methods }}</el-descriptions-item>
            <el-descriptions-item label="主要发现">{{ summaryResult.findings }}</el-descriptions-item>
            <el-descriptions-item label="创新点">{{ summaryResult.innovation }}</el-descriptions-item>
            <el-descriptions-item label="局限性">{{ summaryResult.limitations || '未提及' }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { toolAPI } from '../api'

const props = defineProps({
  document: { type: Object, default: null },
})

const activeTab = ref('translate')

// 翻译
const translateInput = ref('')
const targetLanguage = ref('中文')
const translateLoading = ref(false)
const translateResult = ref('')

const handleTranslate = async () => {
  translateLoading.value = true
  translateResult.value = ''
  try {
    const data = await toolAPI.translate({
      text: translateInput.value,
      target_language: targetLanguage.value,
    })
    translateResult.value = data.translated_text
  } catch (err) {
    ElMessage.error('翻译失败')
  } finally {
    translateLoading.value = false
  }
}

// 摘要解读
const summarizeInput = ref('')
const summarizeLoading = ref(false)
const summaryResult = ref(null)

const handleSummarize = async () => {
  if (!props.document) return
  summarizeLoading.value = true
  summaryResult.value = null
  try {
    const data = await toolAPI.summarize({ document_id: props.document.id })
    summaryResult.value = data.summary
  } catch (err) {
    ElMessage.error('生成解读失败')
  } finally {
    summarizeLoading.value = false
  }
}

const handleSummarizeText = async () => {
  summarizeLoading.value = true
  summaryResult.value = null
  try {
    const data = await toolAPI.summarize({ text: summarizeInput.value })
    summaryResult.value = data.summary
  } catch (err) {
    ElMessage.error('生成解读失败')
  } finally {
    summarizeLoading.value = false
  }
}
</script>

<style scoped>
.tool-panel {
  padding: 4px 0;
}

.hint {
  font-size: 14px;
  color: #606266;
  margin-bottom: 12px;
}

.result-box {
  margin-top: 16px;
  padding: 12px;
  background: #f9f9f9;
  border-radius: 8px;
}

.result-box h4 {
  margin-bottom: 8px;
  color: #303133;
}

.result-box p {
  font-size: 14px;
  line-height: 1.6;
  color: #606266;
  white-space: pre-wrap;
}
</style>
