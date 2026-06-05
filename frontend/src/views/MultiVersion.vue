<template>
  <div>
    <h1>多版本对比</h1>

    <!-- Pass Rate Cards Row -->
    <el-row :gutter="16" style="margin-bottom: 20px;" v-if="passRates.length > 0">
      <el-col :span="8" v-for="pr in passRates" :key="pr.label">
        <PassRateCard
          :title="pr.label"
          :pass-at-k="pr.pass_at_k_pct"
          :pass-power-k="pr.pass_power_k_pct"
          :pp-gap="pr.pp_gap"
        />
      </el-col>
    </el-row>

    <!-- Radar Chart -->
    <el-card header="六维雷达图" style="margin-bottom: 20px;">
      <RadarChart v-if="radarData" :dimensions="radarData.dimensions" :series="radarData.series" />
      <el-empty v-else description="选择 Run ID 进行对比" />
    </el-card>

    <!-- Trend Line -->
    <el-card header="趋势追踪" style="margin-bottom: 20px;">
      <TrendLine
        v-if="trendData"
        :labels="trendData.labels"
        :overall-scores="trendData.overall_scores"
        :pass-at-k-pcts="trendData.pass_at_k_pcts"
        :pass-power-k-pcts="trendData.pass_power_k_pcts"
      />
      <el-empty v-else description="选择 Benchmark 查看趋势" />
    </el-card>

    <!-- Heatmap -->
    <el-card header="题目 × 维度热力图">
      <Heatmap
        v-if="heatmapData"
        :questions="heatmapData.questions"
        :dimensions="heatmapData.dimensions"
        :data="heatmapData.data"
      />
      <el-empty v-else description="选择 Run ID 查看热力图" />
    </el-card>

    <!-- Controls -->
    <el-card style="margin-top: 20px;">
      <template #header>查询控制</template>
      <el-form inline>
        <el-form-item label="Run IDs (逗号分隔)">
          <el-input v-model="runIdsInput" placeholder="uuid1, uuid2" style="width: 400px;" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadComparison">加载对比</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { compareApi } from '../api'
import { ElMessage } from 'element-plus'
import RadarChart from '../components/RadarChart.vue'
import Heatmap from '../components/Heatmap.vue'
import TrendLine from '../components/TrendLine.vue'
import PassRateCard from '../components/PassRateCard.vue'

const runIdsInput = ref('')
const radarData = ref<any>(null)
const heatmapData = ref<any>(null)
const trendData = ref<any>(null)
const passRates = ref<any[]>([])

async function loadComparison() {
  const ids = runIdsInput.value.split(',').map(s => s.trim()).filter(Boolean)
  if (ids.length === 0) {
    ElMessage.warning('请输入至少一个 Run ID')
    return
  }
  try {
    const [radarRes, heatmapRes, passRes] = await Promise.all([
      compareApi.radar(ids.join(',')),
      compareApi.heatmap(ids.join(',')),
      compareApi.passRate(ids.join(',')),
    ])
    radarData.value = radarRes.data
    heatmapData.value = heatmapRes.data
    passRates.value = passRes.data.runs || []

    // Try trend if there's a benchmark pattern
    try {
      const trendRes = await compareApi.trend(ids[0])
      trendData.value = trendRes.data
    } catch {}
    ElMessage.success('对比数据已加载')
  } catch (e: any) {
    ElMessage.error('加载失败: ' + (e.message || ''))
  }
}
</script>
