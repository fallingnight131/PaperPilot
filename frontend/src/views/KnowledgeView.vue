<template>
  <div class="layout">
    <!-- 顶部导航栏 -->
    <el-header class="header">
      <div class="header-left">
        <h2 class="logo" @click="$router.push('/home')" style="cursor:pointer">📚 PaperPilot</h2>
      </div>
      <el-menu mode="horizontal" default-active="/knowledge" router class="nav-menu">
        <el-menu-item index="/home"><el-icon><HomeFilled /></el-icon>首页</el-menu-item>
        <el-menu-item index="/documents"><el-icon><Document /></el-icon>文献管理</el-menu-item>
        <el-menu-item index="/library"><el-icon><Collection /></el-icon>文献库</el-menu-item>
        <el-menu-item index="/knowledge"><el-icon><DataAnalysis /></el-icon>知识库</el-menu-item>
        <el-menu-item index="/chat"><el-icon><ChatDotRound /></el-icon>智能问答</el-menu-item>
        <el-menu-item index="/history"><el-icon><Clock /></el-icon>会话历史</el-menu-item>
      </el-menu>
      <div class="header-right">
        <el-dropdown @command="handleCommand">
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

    <el-main class="main-content">
      <!-- 顶部工具栏 -->
      <div class="toolbar">
        <h3 class="toolbar-title">知识库可视化</h3>
        <el-button type="primary" :loading="loading" @click="loadMapData" icon="RefreshRight">
          {{ hasData ? '刷新' : '生成可视化' }}
        </el-button>
      </div>

      <!-- 统计卡片 -->
      <el-row :gutter="16" v-if="stats">
        <el-col :span="12">
          <el-card class="stat-card">
            <el-statistic title="已就绪文献" :value="stats.doc_count" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card class="stat-card">
            <el-statistic title="向量分块总数" :value="stats.chunk_count" />
          </el-card>
        </el-col>
      </el-row>

      <!-- 地图区域 -->
      <div class="map-section">
        <!-- 未生成 -->
        <div v-if="!hasData && !loading" class="map-placeholder">
          <el-icon :size="64" color="#c0c4cc"><DataAnalysis /></el-icon>
          <p class="placeholder-title">点击「生成可视化」</p>
          <p class="placeholder-desc">
            系统将把文献库所有向量降维到 2D 平面，<br>
            语义相近的分块会聚集在一起，颜色区分不同文献。
          </p>
        </div>

        <!-- 加载中 -->
        <div v-if="loading" class="map-loading">
          <el-icon class="is-loading" :size="48" color="#409eff"><Loading /></el-icon>
          <p>正在计算降维坐标，请稍候...</p>
        </div>

        <!-- ECharts 散点图 -->
        <div v-show="hasData && !loading" ref="chartEl" class="chart-container" />
      </div>

      <!-- 图例 -->
      <div v-if="hasData && !loading" class="legend-section">
        <span class="legend-label">文献图例：</span>
        <span
          v-for="(name, idx) in legendItems"
          :key="idx"
          class="legend-item"
        >
          <span class="legend-dot" :style="{ background: COLORS[idx % COLORS.length] }" />
          {{ name }}
        </span>
      </div>
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { useAuthStore } from '../stores/auth'
import { knowledgeAPI } from '../api'

const router = useRouter()
const authStore = useAuthStore()

const stats = ref(null)
const hasData = ref(false)
const loading = ref(false)
const chartEl = ref(null)
let chart = null

// 20 色板
const COLORS = [
  '#5470c6','#91cc75','#fac858','#ee6666','#73c0de',
  '#3ba272','#fc8452','#9a60b4','#ea7ccc','#37a2ff',
  '#ff6b6b','#ffa07a','#20b2aa','#9370db','#3cb371',
  '#ff8c00','#00ced1','#dc143c','#4682b4','#adff2f',
]

const legendItems = ref([])

const handleCommand = (command) => {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}

const loadMapData = async () => {
  loading.value = true
  try {
    const data = await knowledgeAPI.getMapData()
    stats.value = { doc_count: data.doc_count, chunk_count: data.chunk_count }
    renderChart(data)
    hasData.value = true
  } catch (err) {
    const msg = err?.response?.data?.message || '加载失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const renderChart = (data) => {
  const { points, doc_names } = data

  // 按 color_idx 分组构建 series
  const groups = {}
  for (const p of points) {
    const idx = p.color_idx
    if (!groups[idx]) groups[idx] = []
    groups[idx].push(p)
  }

  // 文献名列表（按 color_idx 排序）
  const sortedIndices = Object.keys(groups).map(Number).sort((a, b) => a - b)
  legendItems.value = sortedIndices.map((idx) => {
    const p = groups[idx][0]
    return doc_names[String(p.doc_id)] || `文献 ${p.doc_id}`
  })

  const series = sortedIndices.map((idx) => ({
    name: legendItems.value[idx] || `series_${idx}`,
    type: 'scatter',
    data: groups[idx].map((p) => ({
      value: [p.x, p.y],
      // 存原始数据供 tooltip 使用
      _title: p.title,
      _preview: p.preview,
      _page: p.page,
      _chunk: p.chunk_index,
    })),
    symbolSize: 7,
    itemStyle: { color: COLORS[idx % COLORS.length], opacity: 0.8 },
    emphasis: { scale: true, itemStyle: { opacity: 1 } },
  }))

  nextTick(() => {
    if (!chart) {
      chart = echarts.init(chartEl.value, null, { renderer: 'canvas' })
      window.addEventListener('resize', () => chart?.resize())
    }
    chart.setOption({
      backgroundColor: '#fff',
      tooltip: {
        trigger: 'item',
        formatter(params) {
          const d = params.data
          return `
            <div style="width:260px;font-size:13px;line-height:1.6;box-sizing:border-box">
              <div style="color:${params.color};font-weight:600;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">${d._title || '未知文献'}</div>
              <div style="color:#999;margin:2px 0">第 ${d._page} 页 · 分块 ${d._chunk}</div>
              <div style="color:#555;white-space:normal;word-break:break-all">${d._preview || ''}</div>
            </div>`
        },
        confine: true,
      },
      xAxis: { show: false, type: 'value' },
      yAxis: { show: false, type: 'value' },
      legend: { show: false },
      series,
    })
  })
}

onMounted(async () => {
  try {
    const data = await knowledgeAPI.getStats()
    stats.value = data
  } catch { /* ignore */ }
})

onBeforeUnmount(() => {
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.layout {
  min-height: 100vh;
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
}

.header-left { display: flex; align-items: center; }
.logo { font-size: 20px; color: #409eff; white-space: nowrap; margin-right: 40px; }
.nav-menu { flex: 1; border-bottom: none; }
.header-right { display: flex; align-items: center; }
.user-info { display: flex; align-items: center; cursor: pointer; gap: 8px; }
.username { font-size: 14px; color: #606266; }

.main-content {
  flex: 1;
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-title {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.stat-card {
  text-align: center;
}

.map-section {
  flex: 1;
  min-height: 580px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.map-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px;
  text-align: center;
}

.placeholder-title {
  font-size: 18px;
  color: #606266;
  margin: 0;
}

.placeholder-desc {
  font-size: 14px;
  color: #909399;
  line-height: 1.8;
  margin: 0;
}

.map-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: #606266;
  font-size: 14px;
}

.chart-container {
  width: 100%;
  height: 580px;
}

.legend-section {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #606266;
  padding: 4px 0;
}

.legend-label {
  color: #909399;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
