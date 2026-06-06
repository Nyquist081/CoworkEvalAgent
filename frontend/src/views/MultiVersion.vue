<template>
  <div>
    <el-button @click="goBack" style="margin-bottom:12px;" icon="ArrowLeft">返回 Dashboard</el-button>
    <h1>📈 多版本对比</h1>
    <el-card>
      <el-form inline>
        <el-form-item label="Run IDs (逗号分隔)">
          <el-input v-model="ids" placeholder="uuid1, uuid2" style="width:400px" />
        </el-form-item>
        <el-form-item label="Benchmark">
          <el-input v-model="benchmarkId" placeholder="用于趋势图" style="width:220px" />
        </el-form-item>
        <el-form-item><el-button type="primary" @click="load">加载对比</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" style="margin-top:16px;" v-if="radar.series.length">
      <el-col :span="12">
        <el-card>
          <template #header>维度雷达</template>
          <RadarChart :dimensions="radar.dimensions" :series="radar.series" />
        </el-card>
      </el-col>
      <el-col :span="12" v-if="trend.labels.length">
        <el-card>
          <template #header>版本趋势</template>
          <TrendLine
            :labels="trend.labels"
            :overall-scores="trend.overall_scores"
            :pass-at-k-pcts="trend.pass_at_k_pcts"
            :pass-power-k-pcts="trend.pass_power_k_pcts"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top:16px;" v-if="heatmap.questions.length">
      <template #header>题目维度热力图</template>
      <Heatmap :questions="heatmap.questions" :dimensions="heatmap.dimensions" :data="heatmap.data" />
    </el-card>

    <el-row :gutter="16" style="margin-top:16px;" v-if="passRates.length">
      <el-col :span="8" v-for="p in passRates" :key="p.label">
        <el-card shadow="hover">
          <template #header>{{ p.label }}</template>
          <el-row>
            <el-col :span="8" style="text-align:center">
              <div style="font-size:28px;font-weight:bold;color:#409eff;">{{ p.pass_at_k_pct }}%</div>
              <div style="font-size:12px;color:#999;">pass@k</div>
            </el-col>
            <el-col :span="8" style="text-align:center">
              <div style="font-size:28px;font-weight:bold;color:#67c23a;">{{ p.pass_power_k_pct }}%</div>
              <div style="font-size:12px;color:#999;">pass^k</div>
            </el-col>
            <el-col :span="8" style="text-align:center">
              <div style="font-size:28px;font-weight:bold;" :style="{color: p.pp_gap>20?'#f56c6c':'#67c23a'}">{{ p.pp_gap }}%</div>
              <div style="font-size:12px;color:#999;">PP 差值</div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>
    <el-empty v-if="!passRates.length && loaded" description="选择 Run IDs 查看对比" />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import RadarChart from '../components/RadarChart.vue'
import Heatmap from '../components/Heatmap.vue'
import TrendLine from '../components/TrendLine.vue'

const API='/coworkeval/v1'
const router = useRouter()
const ids = ref('')
const benchmarkId = ref('')
const passRates = ref<any[]>([])
const loaded = ref(false)
const radar = reactive({ dimensions: [] as string[], series: [] as any[] })
const heatmap = reactive({ questions: [] as string[], dimensions: [] as string[], data: [] as number[][] })
const trend = reactive({
  labels: [] as string[],
  overall_scores: [] as number[],
  pass_at_k_pcts: [] as number[],
  pass_power_k_pcts: [] as number[],
})

function goBack() { router.push({name:'dashboard'}).catch(()=>{window.location.href='/'}) }

async function load() {
  loaded.value = true
  try {
    const runIds = ids.value.split(',').map(id => id.trim()).filter(Boolean)
    const [passRes, radarRes, heatmapRes, trendRes] = await Promise.all([
      axios.get(`${API}/compare/pass-rate`, { params: { run_ids: ids.value } }),
      axios.get(`${API}/compare/radar`, { params: { run_ids: ids.value } }),
      runIds.length ? axios.get(`${API}/compare/heatmap`, { params: { run_ids: runIds[0] } }) : Promise.resolve({ data: null }),
      benchmarkId.value ? axios.get(`${API}/compare/trend`, { params: { benchmark_id: benchmarkId.value } }) : Promise.resolve({ data: null }),
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
  } catch(e) { console.error(e) }
}
</script>
