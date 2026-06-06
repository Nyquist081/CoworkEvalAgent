<template>
  <div class="detail-shell">
    <div class="topbar">
      <el-button @click="goBack">返回评测操作台</el-button>
      <el-button @click="goCompare">加入版本对比</el-button>
    </div>

    <section class="summary-panel">
      <div>
        <p class="eyebrow">评测结果详情</p>
        <h1>{{ run?.run_label || shortId(runId) }}</h1>
        <p>{{ verdictText }}</p>
      </div>
      <div class="score-hero" :class="verdictClass">
        <b>{{ overallAverage }}</b>
        <span>综合得分</span>
      </div>
    </section>

    <div class="dimension-grid" v-if="avgDims.length">
      <el-card shadow="never" class="dim-card" v-for="dim in avgDims" :key="dim.key">
        <b :style="{ color: dim.color }">{{ dim.val }}</b>
        <span>{{ dim.label }}</span>
        <small>{{ dim.help }}</small>
      </el-card>
    </div>

    <el-card shadow="never" class="panel-card">
      <template #header>
        <div class="section-head">
          <div>
            <b>题目明细</b>
            <small>点击任意题目查看工具调用、Token、耗时等细节。</small>
          </div>
          <el-tag>{{ scores.length }} 道题</el-tag>
        </div>
      </template>
      <el-table :data="scores" stripe empty-text="暂无评分数据" @row-click="showDetail">
        <el-table-column prop="question_id" label="题目" min-width="220" show-overflow-tooltip />
        <el-table-column v-for="dim in scoreColumns" :key="dim.key" :label="dim.short" width="86">
          <template #default="{ row }">{{ formatScore(row[dim.key]) }}</template>
        </el-table-column>
        <el-table-column label="总分" width="100">
          <template #default="{ row }">
            <el-tag :type="scoreType(row.overall_score)" size="small">
              {{ formatScore(row.overall_score) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialog" :title="`题目详情：${selectedQid}`" width="720px">
      <div v-if="detail" class="detail-dialog">
        <el-alert :title="detailAdvice" type="info" :closable="false" show-icon />
        <el-descriptions :column="2" border>
          <el-descriptions-item v-for="dim in scoreColumns" :key="dim.key" :label="dim.label">
            {{ formatScore(detail[dim.key]) }}
          </el-descriptions-item>
          <el-descriptions-item label="综合得分" :span="2">
            <el-tag :type="scoreType(detail.overall_score)" size="large">
              {{ formatScore(detail.overall_score) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <el-row :gutter="12">
          <el-col :span="8"><el-statistic title="工具调用" :value="detail.actual_tool_calls || 0" /></el-col>
          <el-col :span="8"><el-statistic title="Token" :value="detail.actual_tokens || 0" /></el-col>
          <el-col :span="8"><el-statistic title="耗时 ms" :value="detail.actual_time_ms || 0" /></el-col>
          <el-col :span="8"><el-statistic title="对话轮次" :value="detail.actual_rounds || 0" /></el-col>
          <el-col :span="8"><el-statistic title="成功调用" :value="detail.actual_success_calls || 0" /></el-col>
          <el-col :span="8"><el-statistic title="成本 $" :value="detail.actual_cost_usd || 0" :precision="4" /></el-col>
        </el-row>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const API = '/coworkeval/v1'
const route = useRoute()
const router = useRouter()
const runId = computed(() => route.params.runId as string)
const run = ref<any>(null)
const scores = ref<any[]>([])
const dialog = ref(false)
const selectedQid = ref('')
const detail = ref<any>(null)

const scoreColumns = [
  { key: 't1_completion', short: '完成', label: '任务完成度', help: '输出是否符合参考答案' },
  { key: 't2_accuracy', short: '准确', label: '工具准确性', help: '工具调用是否成功' },
  { key: 't3_efficiency', short: '效率', label: '工具效率', help: '工具调用是否克制' },
  { key: 't4_thinking', short: '思考', label: '思考效率', help: 'Token 和轮次是否合理' },
  { key: 'e_performance', short: '性能', label: '执行性能', help: '耗时是否接近基准' },
  { key: 'c_cost', short: '成本', label: '成本效率', help: '费用是否接近基准' },
]

const overallAverage = computed(() => {
  if (!scores.value.length) return '-'
  return (scores.value.reduce((total, score) => total + (score.overall_score || 0), 0) / scores.value.length).toFixed(1)
})
const verdictClass = computed(() => {
  const value = Number(overallAverage.value)
  if (value >= 80) return 'good'
  if (value >= 60) return 'ok'
  return 'risk'
})
const verdictText = computed(() => {
  const value = Number(overallAverage.value)
  if (!scores.value.length) return '还没有评分数据。请确认评测是否完成。'
  if (value >= 80) return '整体表现优秀，可以作为一个可用版本继续对比和沉淀。'
  if (value >= 60) return '整体可用，但仍有维度需要优化，建议查看低分题目。'
  return '这个版本风险较高，建议先查看任务完成度和工具调用问题。'
})
const detailAdvice = computed(() => {
  if (!detail.value) return ''
  const value = detail.value.overall_score || 0
  if (value >= 80) return '这道题表现稳定，可以作为后续版本对比的参考。'
  if (value >= 60) return '这道题基本完成，但仍建议检查低分维度。'
  return '这道题需要重点排查，优先查看任务完成度和工具调用。'
})
const avgDims = computed(() => {
  if (!scores.value.length) return []
  const avg = (key: string) => (scores.value.reduce((total, score) => total + (score[key] || 0), 0) / scores.value.length).toFixed(1)
  const colors = ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#64748b', '#7c3aed']
  return scoreColumns.map((column, index) => ({
    ...column,
    val: avg(column.key),
    color: colors[index],
  }))
})

function shortId(id?: string) {
  return id ? id.slice(0, 8) : '-'
}

function formatScore(value?: number) {
  return typeof value === 'number' ? value.toFixed(1) : '-'
}

function scoreType(value?: number) {
  if ((value || 0) >= 80) return 'success'
  if ((value || 0) >= 60) return 'warning'
  return 'danger'
}

function goBack() {
  window.location.assign(router.resolve({ name: 'dashboard' }).href)
}

function goCompare() {
  router.push({ path: '/compare', query: { runs: runId.value } })
}

async function load() {
  try { run.value = (await axios.get(`${API}/runs/${runId.value}`)).data } catch(e) { console.error(e) }
  try { scores.value = (await axios.get(`${API}/runs/${runId.value}/scores`)).data || [] } catch(e) { console.error(e) }
}

async function showDetail(row: any) {
  selectedQid.value = row.question_id
  dialog.value = true
  try { detail.value = (await axios.get(`${API}/runs/${runId.value}/scores/${row.question_id}`)).data }
  catch { detail.value = row }
}

onMounted(load)
</script>

<style scoped>
.detail-shell {
  max-width: 1280px;
  margin: 0 auto;
  text-align: left;
}

.topbar,
.section-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.summary-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 18px;
  margin-bottom: 16px;
}

.summary-panel h1 {
  margin: 4px 0 8px;
  color: #111827;
  font-size: 32px;
  letter-spacing: 0;
}

.eyebrow,
.section-head small {
  color: #667085;
  font-size: 13px;
}

.score-hero {
  display: grid;
  place-items: center;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.score-hero b {
  font-size: 38px;
  line-height: 1;
}

.score-hero.good b { color: #16a34a; }
.score-hero.ok b { color: #d97706; }
.score-hero.risk b { color: #dc2626; }

.dimension-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.dim-card {
  min-height: 138px;
}

.dim-card b,
.dim-card span,
.dim-card small {
  display: block;
}

.dim-card b {
  font-size: 24px;
}

.dim-card span {
  color: #1f2937;
  font-weight: 700;
}

.dim-card small {
  margin-top: 6px;
  color: #667085;
  line-height: 1.35;
}

.panel-card {
  border-radius: 8px;
}

.detail-dialog {
  display: grid;
  gap: 16px;
}

@media (max-width: 960px) {
  .summary-panel {
    grid-template-columns: 1fr;
  }

  .dimension-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
