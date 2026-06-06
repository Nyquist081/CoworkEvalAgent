<template>
  <div class="compare-shell">
    <div class="topbar">
      <el-button @click="goBack">返回评测操作台</el-button>
    </div>

    <section class="summary-panel">
      <div>
        <p class="eyebrow">版本对比</p>
        <h1>比较多个 Agent 版本</h1>
        <p>勾选两个或更多历史结果，平台会自动生成雷达图、热力图和通过率对比。</p>
      </div>
      <el-button type="primary" size="large" :disabled="selectedRunIds.length < 1" :loading="loading" @click="loadComparison">
        生成对比
      </el-button>
    </section>

    <el-card shadow="never" class="panel-card">
      <template #header>
        <div class="section-head">
          <div>
            <b>选择要对比的版本</b>
            <small>不用复制 UUID，直接从历史记录里勾选。</small>
          </div>
          <el-tag>{{ selectedRunIds.length }} 个已选</el-tag>
        </div>
      </template>
      <el-table ref="runsTableRef" :data="runs" row-key="id" empty-text="还没有可对比的评测记录" size="small" max-height="300" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column label="版本" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <b>{{ row.run_label || shortId(row.id) }}</b>
          </template>
        </el-table-column>
        <el-table-column prop="benchmark_id" label="评测集" min-width="150" show-overflow-tooltip />
        <el-table-column label="模型" min-width="130">
          <template #default="{ row }">{{ row.model || '未记录' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'COMPLETED' ? 'success' : 'warning'" size="small">
              {{ row.status === 'COMPLETED' ? '已完成' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-if="loaded && !passRates.length" description="请选择至少一个已完成版本后生成对比" />

    <div v-if="passRates.length" class="metric-list">
      <el-card shadow="never" class="metric-card" v-for="rate in passRates" :key="rate.label">
        <template #header>{{ rate.label }}</template>
        <div class="rate-grid">
          <div>
            <b>{{ rate.pass_at_k_pct }}%</b>
            <span>至少一次通过</span>
          </div>
          <div>
            <b>{{ rate.pass_power_k_pct }}%</b>
            <span>每次都通过</span>
          </div>
          <div>
            <b :class="{ risk: rate.pp_gap > 20 }">{{ rate.pp_gap }}%</b>
            <span>稳定性差距</span>
          </div>
        </div>
      </el-card>
    </div>

    <div v-if="radar.series.length" class="chart-grid">
      <el-card shadow="never">
        <template #header>六维能力对比</template>
        <RadarChart :dimensions="radar.dimensions" :series="radar.series" />
      </el-card>
      <el-card shadow="never" v-if="trend.labels.length">
        <template #header>同一评测集的版本趋势</template>
        <TrendLine
          :labels="trend.labels"
          :overall-scores="trend.overall_scores"
          :pass-at-k-pcts="trend.pass_at_k_pcts"
          :pass-power-k-pcts="trend.pass_power_k_pcts"
        />
      </el-card>
    </div>

    <el-card shadow="never" class="panel-card" v-if="heatmap.questions.length">
      <template #header>首个已选版本的题目热力图</template>
      <Heatmap :questions="heatmap.questions" :dimensions="heatmap.dimensions" :data="heatmap.data" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { nextTick, reactive, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import RadarChart from '../components/RadarChart.vue'
import Heatmap from '../components/Heatmap.vue'
import TrendLine from '../components/TrendLine.vue'

const API = '/coworkeval/v1'
const router = useRouter()
const route = useRoute()

const runs = ref<any[]>([])
const runsTableRef = ref<any>(null)
const selectedRunIds = ref<string[]>([])
const passRates = ref<any[]>([])
const loaded = ref(false)
const loading = ref(false)
const radar = reactive({ dimensions: [] as string[], series: [] as any[] })
const heatmap = reactive({ questions: [] as string[], dimensions: [] as string[], data: [] as number[][] })
const trend = reactive({
  labels: [] as string[],
  overall_scores: [] as number[],
  pass_at_k_pcts: [] as number[],
  pass_power_k_pcts: [] as number[],
})

function shortId(id?: string) {
  return id ? id.slice(0, 8) : '-'
}

function goBack() {
  router.push({ name: 'dashboard' }).catch(() => { window.location.href = '/' })
}

function onSelectionChange(selection: any[]) {
  selectedRunIds.value = selection.map((run) => run.id)
}

async function loadRuns() {
  const res = await axios.get(`${API}/runs`)
  runs.value = (res.data || []).sort((a: any, b: any) => {
    return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
  })
  const queryRuns = String(route.query.runs || '').split(',').filter(Boolean)
  if (queryRuns.length) {
    selectedRunIds.value = queryRuns
    await nextTick()
    runs.value
      .filter((run) => queryRuns.includes(run.id))
      .forEach((run) => runsTableRef.value?.toggleRowSelection(run, true))
  }
}

async function loadComparison() {
  loaded.value = true
  if (!selectedRunIds.value.length) return
  loading.value = true
  try {
    const runIds = selectedRunIds.value.join(',')
    const firstRun = runs.value.find((run) => run.id === selectedRunIds.value[0])
    const [passRes, radarRes, heatmapRes, trendRes] = await Promise.all([
      axios.get(`${API}/compare/pass-rate`, { params: { run_ids: runIds } }),
      axios.get(`${API}/compare/radar`, { params: { run_ids: runIds } }),
      axios.get(`${API}/compare/heatmap`, { params: { run_ids: selectedRunIds.value[0] } }),
      firstRun?.benchmark_id
        ? axios.get(`${API}/compare/trend`, { params: { benchmark_id: firstRun.benchmark_id } })
        : Promise.resolve({ data: null }),
    ])
    passRates.value = passRes.data.runs || []
    radar.dimensions = radarRes.data.dimensions || []
    radar.series = radarRes.data.series || []
    heatmap.questions = heatmapRes.data?.questions || []
    heatmap.dimensions = heatmapRes.data?.dimensions || []
    heatmap.data = heatmapRes.data?.data || []
    trend.labels = trendRes.data?.labels || []
    trend.overall_scores = trendRes.data?.overall_scores || []
    trend.pass_at_k_pcts = trendRes.data?.pass_at_k_pcts || []
    trend.pass_power_k_pcts = trendRes.data?.pass_power_k_pcts || []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadRuns()
  if (selectedRunIds.value.length) await loadComparison()
})
</script>

<style scoped>
.compare-shell {
  max-width: 1280px;
  margin: 0 auto;
  text-align: left;
}

.topbar,
.section-head,
.summary-panel {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.summary-panel {
  margin-bottom: 16px;
}

.summary-panel h1 {
  margin: 4px 0 8px;
  color: #111827;
  font-size: 32px;
  letter-spacing: 0;
}

.summary-panel p,
.section-head small {
  color: #667085;
  font-size: 13px;
}

.eyebrow {
  color: #4f6f9f;
  font-weight: 700;
  text-transform: uppercase;
}

.panel-card,
.metric-list,
.chart-grid {
  margin-bottom: 16px;
}

.metric-list,
.chart-grid {
  display: grid;
  gap: 16px;
}

.metric-list {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.chart-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.rate-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.rate-grid b,
.rate-grid span {
  display: block;
}

.rate-grid b {
  color: #2563eb;
  font-size: 22px;
}

.rate-grid b.risk {
  color: #dc2626;
}

.rate-grid span {
  color: #667085;
  font-size: 12px;
}

@media (max-width: 960px) {
  .summary-panel,
  .section-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .chart-grid,
  .rate-grid {
    grid-template-columns: 1fr;
  }
}
</style>
