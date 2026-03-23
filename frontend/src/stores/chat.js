import { defineStore } from 'pinia'
import { chatAPI } from '../api'

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [],
    currentConversationId: null,
    messages: [],
    loading: false,
  }),

  getters: {
    currentConversation: (state) => {
      return state.conversations.find((c) => c.id === state.currentConversationId)
    },
  },

  actions: {
    async fetchConversations() {
      const data = await chatAPI.getConversations()
      this.conversations = data.conversations || []
    },

    async createConversation(title) {
      const data = await chatAPI.createConversation({ title })
      this.conversations.unshift(data)
      this.currentConversationId = data.id
      this.messages = []
      return data
    },

    async selectConversation(conversationId) {
      this.currentConversationId = conversationId
      await this.fetchMessages(conversationId)
    },

    async fetchMessages(conversationId) {
      const data = await chatAPI.getMessages(conversationId)
      this.messages = data.messages || []
    },

    async askQuestion(question, docIds = null) {
      this.loading = true
      try {
        // 添加用户消息到列表（乐观更新）
        this.messages.push({
          role: 'user',
          content: question,
          sources: [],
          created_at: new Date().toISOString(),
        })

        const data = await chatAPI.ask({
          question,
          conversation_id: this.currentConversationId,
          doc_ids: docIds,
        })

        // 如果是新会话，更新会话ID
        if (!this.currentConversationId) {
          this.currentConversationId = data.conversation_id
          await this.fetchConversations()
        }

        // 添加 AI 回复
        this.messages.push({
          role: 'assistant',
          content: data.answer,
          sources: data.sources || [],
          created_at: new Date().toISOString(),
        })

        return data
      } finally {
        this.loading = false
      }
    },

    async deleteConversation(conversationId) {
      await chatAPI.deleteConversation(conversationId)
      this.conversations = this.conversations.filter((c) => c.id !== conversationId)
      if (this.currentConversationId === conversationId) {
        this.currentConversationId = null
        this.messages = []
      }
    },

    clearCurrent() {
      this.currentConversationId = null
      this.messages = []
    },
  },
})
