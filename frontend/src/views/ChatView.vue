<template>
  <div class="chat-layout">
    <!-- 顶部导航栏 -->
    <el-header class="header">
      <div class="header-left">
        <h2 class="logo" @click="$router.push('/home')" style="cursor:pointer">📚 PaperPilot</h2>
      </div>
      <el-menu mode="horizontal" default-active="/chat" router class="nav-menu">
        <el-menu-item index="/home"><el-icon><HomeFilled /></el-icon>首页</el-menu-item>
        <el-menu-item index="/documents"><el-icon><Document /></el-icon>文献管理</el-menu-item>
        <el-menu-item index="/chat"><el-icon><ChatDotRound /></el-icon>智能问答</el-menu-item>
        <el-menu-item index="/history"><el-icon><Clock /></el-icon>会话历史</el-menu-item>
      </el-menu>
      <div class="header-right">
        <el-dropdown @command="handleHeaderCommand">
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

    <div class="chat-body">
      <!-- 左侧会话列表 -->
      <aside class="sidebar">
        <el-button type="primary" class="new-chat-btn" @click="handleNewChat" icon="Plus">
          新建会话
        </el-button>

        <div class="conversation-list">
          <div
            v-for="conv in chatStore.conversations"
            :key="conv.id"
            :class="['conv-item', { active: conv.id === chatStore.currentConversationId }]"
            @click="selectConversation(conv.id)"
          >
            <el-icon><ChatDotSquare /></el-icon>
            <span class="conv-title">{{ conv.title }}</span>
            <el-icon class="conv-delete" @click.stop="deleteConversation(conv.id)"><Delete /></el-icon>
          </div>
          <el-empty v-if="chatStore.conversations.length === 0" description="暂无会话" :image-size="60" />
        </div>
      </aside>

      <!-- 主聊天区域 -->
      <main class="chat-main">
        <div class="messages-container" ref="messagesContainer">
          <div v-if="chatStore.messages.length === 0 && !chatStore.loading" class="empty-chat">
            <div class="empty-icon">🤖</div>
            <h3>开始智能问答</h3>
            <p>上传电化学储能材料领域的文献，然后在这里提问</p>
          </div>

          <chat-message
            v-for="(msg, idx) in chatStore.messages"
            :key="idx"
            :message="msg"
          />

          <!-- 加载动画 -->
          <div v-if="chatStore.loading" class="typing-indicator">
            <div class="typing-avatar">🤖</div>
            <div class="typing-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>

        <!-- 底部输入区 -->
        <div class="input-area">
          <!-- 文献范围选择 -->
          <div class="doc-selector" v-if="showDocSelector">
            <el-select v-model="selectedDocIds" multiple placeholder="限定检索范围（可选）" clearable style="width: 100%">
              <el-option
                v-for="doc in availableDocs"
                :key="doc.id"
                :label="doc.title"
                :value="doc.id"
              />
            </el-select>
          </div>
          <div class="input-row">
            <el-button text @click="showDocSelector = !showDocSelector" :type="showDocSelector ? 'primary' : ''">
              <el-icon><FolderOpened /></el-icon>
            </el-button>
            <el-input
              v-model="inputText"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              placeholder="输入您的问题...（Enter 发送，Shift+Enter 换行）"
              @keydown="handleKeydown"
              class="message-input"
            />
            <el-button
              type="primary"
              icon="Promotion"
              :loading="chatStore.loading"
              :disabled="!inputText.trim()"
              @click="sendMessage"
              circle
              size="large"
            />
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import { documentAPI } from '../api'
import ChatMessage from '../components/ChatMessage.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const chatStore = useChatStore()

const messagesContainer = ref(null)
const inputText = ref('')
const selectedDocIds = ref([])
const showDocSelector = ref(false)
const availableDocs = ref([])

const handleHeaderCommand = (command) => {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}

const handleNewChat = () => {
  chatStore.clearCurrent()
}

const selectConversation = async (convId) => {
  await chatStore.selectConversation(convId)
  scrollToBottom()
}

const deleteConversation = async (convId) => {
  try {
    await ElMessageBox.confirm('确定要删除此会话吗？', '提示', { type: 'warning' })
    await chatStore.deleteConversation(convId)
    ElMessage.success('会话已删除')
  } catch {
    // 取消
  }
}

const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

const sendMessage = async () => {
  const question = inputText.value.trim()
  if (!question || chatStore.loading) return

  inputText.value = ''
  try {
    await chatStore.askQuestion(question, selectedDocIds.value.length > 0 ? selectedDocIds.value : null)
    scrollToBottom()
  } catch (err) {
    ElMessage.error('问答失败，请稍后重试')
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    const container = messagesContainer.value
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  })
}

// 消息变化时自动滚动
watch(() => chatStore.messages.length, () => {
  scrollToBottom()
})

onMounted(async () => {
  await chatStore.fetchConversations()

  // 获取可用文献列表
  try {
    const data = await documentAPI.getList({ page: 1, per_page: 100, search: '' })
    availableDocs.value = (data.documents || []).filter((d) => d.status === 'ready')
  } catch {
    // ignore
  }

  // 如果 URL 参数指定了会话
  const convId = route.query.conversation_id
  if (convId) {
    await chatStore.selectConversation(Number(convId))
    scrollToBottom()
  }
})
</script>

<style scoped>
.chat-layout {
  height: 100vh;
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
  flex-shrink: 0;
}

.header-left { display: flex; align-items: center; }
.logo { font-size: 20px; color: #409eff; white-space: nowrap; margin-right: 40px; }
.nav-menu { flex: 1; border-bottom: none; }
.header-right { display: flex; align-items: center; }
.user-info { display: flex; align-items: center; cursor: pointer; gap: 8px; }
.username { font-size: 14px; color: #606266; }

.chat-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 侧边栏 */
.sidebar {
  width: 260px;
  background: #f7f8fa;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  padding: 16px;
  flex-shrink: 0;
}

.new-chat-btn {
  width: 100%;
  margin-bottom: 16px;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
}

.conv-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.2s;
  gap: 8px;
}

.conv-item:hover {
  background: #e8eaed;
}

.conv-item.active {
  background: #d0e3ff;
}

.conv-title {
  flex: 1;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-delete {
  opacity: 0;
  transition: opacity 0.2s;
  color: #909399;
}

.conv-item:hover .conv-delete {
  opacity: 1;
}

.conv-delete:hover {
  color: #f56c6c;
}

/* 聊天主区域 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.empty-chat {
  text-align: center;
  margin-top: 120px;
  color: #909399;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-chat h3 {
  font-size: 20px;
  color: #606266;
  margin-bottom: 8px;
}

/* 打字动画 */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
}

.typing-avatar {
  font-size: 28px;
}

.typing-dots {
  display: flex;
  gap: 4px;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  background: #409eff;
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}

/* 输入区 */
.input-area {
  border-top: 1px solid #e4e7ed;
  padding: 16px 24px;
  background: white;
  flex-shrink: 0;
}

.doc-selector {
  margin-bottom: 8px;
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.message-input {
  flex: 1;
}

.message-input :deep(.el-textarea__inner) {
  resize: none;
  border-radius: 8px;
}
</style>
