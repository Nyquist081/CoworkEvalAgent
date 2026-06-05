<template>
  <div>
    <h1>评测概览</h1>

    <!-- Summary Cards -->
    <el-row :gutter="20" style="margin-bottom: 24px;">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="评测任务总数" :value="stats.totalRuns" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="已完成" :value="stats.completedRuns">
            <template #suffix>
              <el-tag type="success" size="small">{{ completionRate }}%</el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="平均总分" :value="stats.avgOverall" :precision="1" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="评测集数量" :value="stats.totalManifests" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Task Runs Table -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>评测任务列表</span>
          <el-button type="primary" size="small" @click="refresh">刷新</el-button>
        </div>
      </template>
      <el-table :data="runs" v-loading="loading" stripe>
        <el-table-column prop="id" label="Run ID" width="120">
          <template #default="{ row }">
            <el-link type="primary" @click="goToRun(row.id)">{{ row.id?.substring(0, 8) }}...</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="benchmark_id" label="Benchmark" width="150" />
        <el-table-column prop="status" label="状态" width="140">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="goToRun(row.id)">详情</el-button>
            <el-button size="small" type="danger" @click="deleteRun(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { runsApi, scoresApi, manifestsApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const loading = ref(false)
const runs = ref<any[]>([])

const stats = reactive({
  totalRuns: 0,
  completedRuns: 0,
  avgOverall: 0,
  totalManifests: 0,
})

const completionRate = computed(() => {
  if (stats.totalRuns === 0) return 0
  return Math.round((stats.completedRuns / stats.totalRuns) * 100)
})

async function refresh() {
  loading.value = true
  try {
    const [runsRes, manifestsRes] = await Promise.all([
      runsApi.list(),
      manifestsApi.list(),
    ])
    runs.value = runsRes.data
    stats.totalRuns = runs.value.length
    stats.completedRuns = runs.value.filter((r: any) => r.status === 'COMPLETED').length
    stats.totalManifests = manifestsRes.data.length

    // Compute average overall score across completed runs
    let totalScore = 0
    let scoreCount = 0
    for (const run of runs.value) {
      if (run.status === 'COMPLETED') {
        try {
          const summary = await scoresApi.summary(run.id)
          totalScore += summary.data.overall_avg || 0
          scoreCount++
        } catch {}
      }
    }
    stats.avgOverall = scoreCount > 0 ? totalScore / scoreCount : 0
  } catch (e: any) {
    ElMessage.error('加载失败: ' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

function goToRun(runId: string) {
  router.push(`/runs/${runId}`)
}

async function deleteRun(runId: string) {
  try {
    await ElMessageBox.confirm('确定删除此评测任务？', '确认', { type: 'warning' })
    await runsApi.delete(runId)
    ElMessage.success('已删除')
    await refresh()
  } catch {}
}

function statusTag(status: string): 'success' | 'warning' | 'danger' | 'info' {
  switch (status) {
    case 'COMPLETED': return 'success'
    case 'FAILED': return 'danger'
    case 'PENDING': return 'info'
    default: return 'warning'
  }
}

function formatDate(d: string) {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-CN')
}

onMounted(refresh)
</script>
