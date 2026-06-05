<template>
  <div>
    <h1>🔬 CoworkEval 评测平台</h1>

    <!-- Upload & Evaluate -->
    <el-card style="margin-bottom: 20px; background: #f0f9ff;">
      <template #header><span style="font-weight: bold;">📤 评测 Trace 文件</span></template>
      <el-form :inline="true">
        <el-form-item label="评测集">
          <el-select v-model="evalForm.benchmark_id" placeholder="选择评测集" @change="onBenchmarkChange">
            <el-option v-for="m in manifests" :key="m.benchmark_id" :label="m.benchmark_id" :value="m.benchmark_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="题目">
          <el-select v-model="evalForm.question_id" placeholder="选择题号">
            <el-option v-for="q in selectedQuestions" :key="q.question_id" :label="`${q.question_id}: ${q.question_name}`" :value="q.question_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Trace 文件">
          <input type="file" accept=".jsonl" @change="onFileSelected" ref="fileInputRef" style="display:none;" />
          <el-button @click="fileInputRef?.click()">
            {{ evalForm.fileName || '选择 .jsonl 文件' }}
          </el-button>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="runEvaluation" :loading="evaluating" :disabled="!canEvaluate">
            🚀 评测
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Evaluation Result -->
    <el-card v-if="evalResult" style="margin-bottom: 20px; border: 2px solid #409eff;">
      <template #header>
        <span style="font-weight: bold;">📊 评测结果 — {{ evalResult.question_id }}</span>
      </template>
      <el-row :gutter="16">
        <el-col :span="4" v-for="d in evalDimensions" :key="d.key">
          <div style="text-align: center; padding: 8px;">
            <div style="font-size: 24px; font-weight: bold;" :style="{color: d.color}">{{ d.value }}</div>
            <div style="font-size: 12px; color: #666;">{{ d.label }}</div>
          </div>
        </el-col>
      </el-row>
      <el-divider />
      <el-descriptions :column="3" size="small">
        <el-descriptions-item label="工具调用">{{ evalResult.metrics.tool_calls }}</el-descriptions-item>
        <el-descriptions-item label="成功">{{ evalResult.metrics.success_calls }}</el-descriptions-item>
        <el-descriptions-item label="Token">{{ evalResult.metrics.tokens?.toLocaleString() }}</el-descriptions-item>
        <el-descriptions-item label="轮次">{{ evalResult.metrics.rounds }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ evalResult.metrics.duration_ms }}ms</el-descriptions-item>
        <el-descriptions-item label="成本">${{ evalResult.metrics.cost_usd }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- Task History -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between;">
          <span>📋 评测历史</span>
          <el-button size="small" @click="refresh">刷新</el-button>
        </div>
      </template>
      <el-table :data="runs" v-loading="loading" stripe empty-text="暂无评测记录，上传 Trace 开始评测">
        <el-table-column prop="benchmark_id" label="评测集" width="180" />
        <el-table-column label="Run ID" width="120">
          <template #default="{ row }">
            <el-link type="primary" @click="goToRun(row.id)">{{ row.id?.substring(0, 8) }}...</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作">
          <template #default="{ row }">
            <el-button size="small" @click="goToRun(row.id)">查看详情</el-button>
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
import { runsApi, manifestsApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const fileInputRef = ref<HTMLInputElement | null>(null)
const loading = ref(false)
const evaluating = ref(false)
const runs = ref<any[]>([])
const manifests = ref<any[]>([])
const selectedQuestions = ref<any[]>([])
const evalResult = ref<any>(null)

const evalForm = reactive({
  benchmark_id: '',
  question_id: '',
  fileName: '',
  file: null as File | null,
})

const canEvaluate = computed(() =>
  evalForm.benchmark_id && evalForm.question_id && evalForm.file
)

const evalDimensions = computed(() => {
  if (!evalResult.value) return []
  const s = evalResult.value.scores
  return [
    { key: 't1', label: 'T1 完成度', value: s.t1_completion?.toFixed(1) ?? '-', color: '#409eff' },
    { key: 't2', label: 'T2 准确率', value: s.t2_accuracy?.toFixed(1) ?? '-', color: '#67c23a' },
    { key: 't3', label: 'T3 效率', value: s.t3_efficiency?.toFixed(1) ?? '-', color: '#e6a23c' },
    { key: 't4', label: 'T4 思考', value: s.t4_thinking?.toFixed(1) ?? '-', color: '#f56c6c' },
    { key: 'e', label: 'E 性能', value: s.e_performance?.toFixed(1) ?? '-', color: '#909399' },
    { key: 'c', label: 'C 成本', value: s.c_cost?.toFixed(1) ?? '-', color: '#b37feb' },
  ]
})

function onBenchmarkChange(bid: string) {
  const m = manifests.value.find((x: any) => x.benchmark_id === bid)
  selectedQuestions.value = m?.questions || []
  evalForm.question_id = ''
}

function onFileSelected(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.[0]) {
    evalForm.file = target.files[0]
    evalForm.fileName = target.files[0].name
  }
}

async function runEvaluation() {
  if (!canEvaluate.value) return
  evaluating.value = true
  evalResult.value = null
  try {
    const form = new FormData()
    form.append('benchmark_id', evalForm.benchmark_id)
    form.append('question_id', evalForm.question_id)
    form.append('trace_file', evalForm.file!)
    form.append('judge_enabled', 'false')

    const res = await axios.post('http://localhost:8000/coworkeval/v1/runs/evaluate', form)
    evalResult.value = res.data
    ElMessage.success('评测完成！')
    await refresh()
  } catch (e: any) {
    ElMessage.error('评测失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    evaluating.value = false
  }
}

async function refresh() {
  loading.value = true
  try {
    const [runsRes, manifestsRes] = await Promise.all([
      runsApi.list(),
      manifestsApi.list(),
    ])
    runs.value = runsRes.data || []
    manifests.value = manifestsRes.data || []
    if (manifests.value.length > 0 && !evalForm.benchmark_id) {
      evalForm.benchmark_id = manifests.value[0].benchmark_id
      onBenchmarkChange(evalForm.benchmark_id)
    }
  } catch (e: any) {
    console.error('Load error:', e)
  } finally {
    loading.value = false
  }
}

function goToRun(runId: string) {
  router.push(`/runs/${runId}`)
}

async function deleteRun(runId: string) {
  try {
    await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' })
    await runsApi.delete(runId)
    ElMessage.success('已删除')
    await refresh()
  } catch {}
}

function statusTag(s: string): any {
  return s === 'COMPLETED' ? 'success' : s === 'FAILED' ? 'danger' : s === 'PENDING' ? 'info' : 'warning'
}

function formatDate(d: string) {
  return d ? new Date(d).toLocaleString('zh-CN') : ''
}

onMounted(refresh)
</script>
