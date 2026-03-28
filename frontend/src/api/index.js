import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

// 创建 axios 实例
const request = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器：自动附加 Authorization header
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：统一处理错误和数据格式
request.interceptors.response.use(
  (response) => {
    const res = response.data
    // 统一格式：{"code": 0, "data": {...}, "message": "success"}
    if (res.code === 0) {
      return res.data
    }
    // 业务错误
    ElMessage.error(res.message || '请求失败')
    return Promise.reject(new Error(res.message || '请求失败'))
  },
  (error) => {
    if (error.response) {
      const status = error.response.status
      const data = error.response.data

      if (status === 401) {
        ElMessage.error('登录已过期，请重新登录')
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        router.push('/login')
      } else if (status === 413) {
        ElMessage.error('文件大小超过限制（最大 50MB）')
      } else {
        ElMessage.error(data?.message || `请求失败 (${status})`)
      }
    } else if (error.message?.includes('timeout')) {
      ElMessage.error('请求超时，请稍后重试')
    } else {
      ElMessage.error('网络错误，请检查连接')
    }
    return Promise.reject(error)
  }
)

// ============ 认证 API ============
export const authAPI = {
  register(data) {
    return request.post('/auth/register', data)
  },
  login(data) {
    return request.post('/auth/login', data)
  },
  getMe() {
    return request.get('/auth/me')
  },
  logout() {
    return request.post('/auth/logout')
  },
}

// ============ 文献 API ============
export const documentAPI = {
  upload(formData) {
    return request.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
  },
  getList(params) {
    return request.get('/documents', { params })
  },
  get(id) {
    return request.get(`/documents/${id}`)
  },
  getDetail(id) {
    return request.get(`/documents/${id}`)
  },
  update(id, data) {
    return request.put(`/documents/${id}`, data)
  },
  delete(id) {
    return request.delete(`/documents/${id}`)
  },
  getStatus(id) {
    return request.get(`/documents/${id}/status`)
  },
  getPreviewUrl(id, page) {
    const token = localStorage.getItem('token')
    const pageFragment = page > 0 ? `#page=${page}` : ''
    return `/api/documents/${id}/preview?token=${encodeURIComponent(token)}${pageFragment}`
  },
}

// ============ 对话 API ============
export const chatAPI = {
  createConversation(data) {
    return request.post('/chat/conversations', data)
  },
  getConversations() {
    return request.get('/chat/conversations')
  },
  getMessages(conversationId) {
    return request.get(`/chat/conversations/${conversationId}/messages`)
  },
  ask(data) {
    return request.post('/chat/ask', data)
  },
  deleteConversation(conversationId) {
    return request.delete(`/chat/conversations/${conversationId}`)
  },
}

// ============ 工具 API ============
export const toolAPI = {
  translate(data) {
    return request.post('/tools/translate', data)
  },
  summarize(data) {
    return request.post('/tools/summarize', data)
  },
  listTools() {
    return request.get('/tools/list')
  },
}

export default request
