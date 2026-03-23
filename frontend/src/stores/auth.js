import { defineStore } from 'pinia'
import { authAPI } from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    token: localStorage.getItem('token') || '',
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    currentUser: (state) => state.user,
  },

  actions: {
    async login(email, password) {
      const data = await authAPI.login({ email, password })
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user))
      return data
    },

    async register(username, email, password) {
      const data = await authAPI.register({ username, email, password })
      return data
    },

    async fetchMe() {
      try {
        const data = await authAPI.getMe()
        this.user = data
        localStorage.setItem('user', JSON.stringify(data))
        return data
      } catch (err) {
        this.logout()
        throw err
      }
    },

    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})
