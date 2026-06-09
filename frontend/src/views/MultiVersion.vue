<template>
  <div class="compare-shell">
    <div class="topbar">
      <el-button @click="goBack">返回评测操作台</el-button>
    </div>

    <section class="summary-panel">
      <div>
        <p class="eyebrow">版本对比</p>
        <h1>比较多个 Agent 版本</h1>
        <p>勾选两个或更多历史结果，平台会自动生成雷达图、热力图和通过率对比。分数越高越好，60 分以下通常需要回看 Trace 或输出文件。</p>
      </div>
      <el-button type="primary" size="large" :disabled="selectedRunIds.length < 1" :loading="loading" @click="loadComparison">
        生成对比
      </el-button>
    </section>

    <el-card shadow="never" class="panel-card">
      <div class="how-to-read">
        <div v-for="item in readingGuide" :key="item.title">
          <b>{{ item.title }}</b>
          <span>{{ item.text }}</span>
        </div>
      </div>
    </el-card>

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
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :type="isSelected(row.id) ? 'primary' : 'default'" @click="toggleRun(row)">
              {{ isSelected(row.id) ? '取消' : '选择' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-if="loaded && !passRates.length" description="请选择至少一个已完成版本后生成对比" />

    <el-alert
      v-if="observabilityRuns.some((item) => !item.can_claim_winner)"
      class="panel-alert"
      type="warning"
      show-icon
      :closable="false"
      title="有版本的 Trace 观测不完整，本次对比不能只按裸分判断胜负"
      description="缺失 tool result 会降低采集可信度。工具成功率只代表已观测部分，不能掩盖 harness 采集质量问题。"
    />

    <div v-if="observabilityRuns.length" class="metric-list">
      <el-card shadow="never" class="metric-card" v-for="item in observabilityRuns" :key="item.label">
        <template #header>
          <div class="section-head compact">
            <b>{{ item.label }}</b>
            <el-tag size="small" :type="item.can_claim_winner ? 'success' : 'warning'">
              {{ item.can_claim_winner ? '可正常比较' : '不可直接判胜' }}
            </el-tag>
          </div>
        </template>
        <div class="rate-grid observability-grid">
          <div>
            <b :class="{ risk: item.trace_observability_rate < 100 }">{{ item.trace_observability_rate }}%</b>
            <span>Trace 观测完整率</span>
          </div>
          <div>
            <b>{{ item.agent_tool_success_rate }}%</b>
            <span>Agent 工具成功率（已观测）</span>
          </div>
          <div>
            <b :class="{ risk: item.missing_tool_results > 0 }">{{ item.missing_tool_results }}</b>
            <span>缺失 tool result</span>
          </div>
        </div>
      </el-card>
    </div>

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
        <template #header>
          <div class="section-head compact">
            <div>
              <b>六维能力对比</b>
              <small>外圈代表更好，某一维明显凹陷就是这个版本的主要短板。</small>
            </div>
          </div>
        </template>
        <RadarChart :dimensions="radar.dimensions" :series="radar.series" />
      </el-card>
      <el-card shadow="never" v-if="trend.labels.length">
        <template #header>
          <div class="section-head compact">
            <div>
              <b>同一评测集的版本趋势</b>
              <small>用于观察后续版本是否在稳定提升，而不是只看某一次偶然高分。</small>
            </div>
          </div>
        </template>
        <TrendLine
          :labels="trend.labels"
          :overall-scores="trend.overall_scores"
          :pass-at-k-pcts="trend.pass_at_k_pcts"
          :pass-power-k-pcts="trend.pass_power_k_pcts"
        />
      </el-card>
    </div>

    <el-card shadow="never" class="panel-card" v-if="radar.series.length">
      <template #header>
        <div class="section-head compact">
          <div>
            <b>六维指标说明</b>
            <small>这些缩写来自工业报告的 TTTEC 评分框架。</small>
          </div>
        </div>
      </template>
      <div class="dimension-help-grid">
        <div v-for="dim in dimensionHelp" :key="dim.key" class="dimension-help">
          <strong>{{ dim.key }}</strong>
          <div>
            <b>{{ dim.name }}</b>
            <span>{{ dim.description }}</span>
            <small>{{ dim.action }}</small>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="panel-card" v-if="heatmap.questions.length">
      <template #header>
        <div class="section-head compact">
          <div>
            <b>首个已选版本的题目热力图</b>
            <small>横向看某道题哪一维低，纵向看某个维度是否在多题上反复出问题。</small>
          </div>
        </div>
      </template>
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
const observabilityRuns = ref<any[]>([])
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

const readingGuide = [
  {
    title: '先看通过率',
    text: 'pass@k 表示至少一次过，pass^k 表示每次都过。两者差距越大，说明稳定性越差。',
  },
  {
    title: '同时看采集可信度',
    text: 'Trace 观测完整率低时，工具成功率可能虚高；这类版本不能直接宣称胜出。',
  },
  {
    title: '再看六维雷达',
    text: '雷达图不是总分排名，而是告诉你版本强弱结构：完成度、工具、效率、成本分别哪里强。',
  },
]

const dimensionHelp = [
  {
    key: 'T1',
    name: '任务完成度',
    description: '输出结果是否真正满足题目要求，通常会和参考答案、文件结果或关键字段比对。',
    action: '低分时先检查最终输出，而不是先看工具调用数量。',
  },
  {
    key: 'T2',
    name: '工具准确性',
    description: '工具调用是否成功、是否少走错路、是否存在失败重试或错误工具选择。',
    action: '低分时回看 Trace 里的失败调用、错误参数和重复尝试。',
  },
  {
    key: 'T3',
    name: '执行效率',
    description: '完成同样任务用了多少工具调用，越接近或优于 baseline 越好。',
    action: '低分通常意味着流程太绕，Skill 应该补更明确的步骤或脚本。',
  },
  {
    key: 'T4',
    name: '思考效率',
    description: 'Token 和对话轮次是否合理，避免长时间犹豫、反复分析或上下文膨胀。',
    action: '低分时检查是否有无效推理、重复读取、过长上下文。',
  },
  {
    key: 'E',
    name: '执行性能',
    description: '耗时是否接近基准，体现实际运行速度和等待成本。',
    action: '低分时看是否有慢工具、串行等待、无必要的大文件处理。',
  },
  {
    key: 'C',
    name: '成本效率',
    description: '费用是否接近基准，主要受 token、模型调用和外部工具成本影响。',
    action: '低分时优先压缩上下文、减少重复调用、降低不必要的大模型判断。',
  },
]

function shortId(id?: string) {
  return id ? id.slice(0, 8) : '-'
}

function goBack() {
  router.push({ name: 'dashboard' }).catch(() => { window.location.href = '/' })
}

function onSelectionChange(selection: any[]) {
  selectedRunIds.value = selection.map((run) => run.id)
}

function isSelected(runId: string) {
  return selectedRunIds.value.includes(runId)
}

function toggleRun(run: any) {
  runsTableRef.value?.toggleRowSelection(run, !isSelected(run.id))
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
    const [passRes, observabilityRes, radarRes, heatmapRes, trendRes] = await Promise.all([
      axios.get(`${API}/compare/pass-rate`, { params: { run_ids: runIds } }),
      axios.get(`${API}/compare/observability`, { params: { run_ids: runIds } }),
      axios.get(`${API}/compare/radar`, { params: { run_ids: runIds } }),
      axios.get(`${API}/compare/heatmap`, { params: { run_ids: selectedRunIds.value[0] } }),
      firstRun?.benchmark_id
        ? axios.get(`${API}/compare/trend`, { params: { benchmark_id: firstRun.benchmark_id } })
        : Promise.resolve({ data: null }),
    ])
    passRates.value = passRes.data.runs || []
    observabilityRuns.value = observabilityRes.data.runs || []
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
.panel-alert,
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

.how-to-read,
.dimension-help-grid {
  display: grid;
  gap: 12px;
}

.how-to-read {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.how-to-read > div,
.dimension-help {
  min-width: 0;
  border: 1px solid #e7eaf0;
  border-radius: 8px;
  background: #fff;
}

.how-to-read > div {
  padding: 14px;
}

.how-to-read b,
.how-to-read span,
.dimension-help b,
.dimension-help span,
.dimension-help small {
  display: block;
}

.how-to-read b {
  color: #172033;
  font-size: 14px;
}

.how-to-read span {
  margin-top: 6px;
  color: #667085;
  font-size: 13px;
  line-height: 1.55;
}

.chart-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.dimension-help-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.dimension-help {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: 12px;
  padding: 14px;
}

.dimension-help strong {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 8px;
  color: #1d4ed8;
  background: #e8f0ff;
  font-size: 18px;
}

.dimension-help b {
  color: #172033;
  font-size: 14px;
}

.dimension-help span {
  margin-top: 4px;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.5;
}

.dimension-help small {
  margin-top: 8px;
  color: #7a8495;
  font-size: 12px;
  line-height: 1.45;
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

.observability-grid b {
  color: #0f766e;
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
  .rate-grid,
  .how-to-read,
  .dimension-help-grid {
    grid-template-columns: 1fr;
  }
}
</style>
