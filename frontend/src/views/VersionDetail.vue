<template>
  <div>
    <el-page-header @back="$router.push('/')" title="返回">
      <template #content>
        <span style="font-size: 18px;">版本详情 — {{ runId }}</span>
      </template>
    </el-page-header>

    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="4" v-for="dim in dimensions" :key="dim.key">
        <el-card shadow="hover" :body-style="{ padding: '16px', textAlign: 'center' }">
          <div style="font-size: 28px; font-weight: bold;" :style="{ color: dim.color }">
            {{ dim.value?.toFixed(1) ?? '-' }}
          </div>
          <div style="margin-top: 4px; font-size: 13px; color: #666;">{{ dim.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px;">
      <template #header><span>题目评分列表</span></template>
      <el-table :data="scores" v-loading="loading" stripe @row-click="showDetail" style="cursor: pointer;">
        <el-table-column prop="question_id" label="题目 ID" width="200" />
        <el-table-column label="T1 完成度" width="100">
          <template #default="{ row }">{{ row.t1_completion?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="T2 准确率" width="100">
          <template #default="{ row }">{{ row.t2_accuracy?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="T3 效率" width="100">
          <template #default="{ row }">{{ row.t3_efficiency?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="T4 思考" width="100">
          <template #default="{ row }">{{ row.t4_thinking?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="E 性能" width="100">
          <template #default="{ row }">{{ row.e_performance?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="C 成本" width="100">
          <template #default="{ row }">{{ row.c_cost?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="总分" width="100">
          <template #default="{ row }">
            <el-tag :type="scoreTag(row.overall_score)">{{ row.overall_score?.toFixed(1) ?? '-' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Score Detail Dialog -->
    <el-dialog v-model="dialogVisible" :title="'题目详情: ' + selectedQuestion" width="800px">
      <ScoreBreakdown v-if="selectedQuestion" :run-id="runId!" :question-id="selectedQuestion" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { scoresApi } from '../api'
import { ElMessage } from 'element-plus'
import ScoreBreakdown from '../components/ScoreBreakdown.vue'

const route = useRoute()
const runId = computed(() => route.params.runId as string)

const loading = ref(false)
const scores = ref<any[]>([])
const dialogVisible = ref(false)
const selectedQuestion = ref('')

const dimensions = computed(() => {
  if (scores.value.length === 0) return defaultDims()
  const avg = (key: string) => {
    const vals = scores.value.map((s: any) => s[key] ?? 0)
    return vals.reduce((a: number, b: number) => a + b, 0) / vals.length
  }
  return [
    { key: 't1', label: 'T1 任务完成度', value: avg('t1_completion'), color: '#409eff' },
    { key: 't2', label: 'T2 工具准确率', value: avg('t2_accuracy'), color: '#67c23a' },
    { key: 't3', label: 'T3 工具效率', value: avg('t3_efficiency'), color: '#e6a23c' },
    { key: 't4', label: 'T4 思考效率', value: avg('t4_thinking'), color: '#f56c6c' },
    { key: 'e', label: 'E 端到端性能', value: avg('e_performance'), color: '#909399' },
    { key: 'c', label: 'C 成本效率', value: avg('c_cost'), color: '#b37feb' },
  ]
})

function defaultDims() {
  return ['t1','t2','t3','t4','e','c'].map(k => ({
    key: k, label: k.toUpperCase(), value: null, color: '#ccc'
  }))
}

function scoreTag(v: number | null) {
  if (v == null) return 'info'
  if (v >= 80) return 'success'
  if (v >= 60) return 'warning'
  return 'danger'
}

function showDetail(row: any) {
  selectedQuestion.value = row.question_id
  dialogVisible.value = true
}

onMounted(async () => {
  loading.value = true
  try {
    const res = await scoresApi.list(runId.value)
    scores.value = res.data
  } catch (e: any) {
    ElMessage.error('加载评分失败: ' + (e.message || ''))
  } finally {
    loading.value = false
  }
})
</script>
