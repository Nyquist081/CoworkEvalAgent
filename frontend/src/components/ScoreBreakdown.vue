<template>
  <div v-loading="loading">
    <el-descriptions :column="2" border v-if="score">
      <el-descriptions-item label="T1 任务完成度">
        {{ score.t1_completion?.toFixed(1) ?? '-' }}
        <el-tag size="small" v-if="score.t1_baseline_only != null" type="info" style="margin-left: 8px;">
          Baseline: {{ score.t1_baseline_only.toFixed(1) }}
        </el-tag>
        <el-tag size="small" v-if="score.t1_judge_only != null" type="warning" style="margin-left: 4px;">
          Judge: {{ score.t1_judge_only.toFixed(1) }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="T2 工具准确率">{{ score.t2_accuracy?.toFixed(1) ?? '-' }}</el-descriptions-item>
      <el-descriptions-item label="T3 工具效率">{{ score.t3_efficiency?.toFixed(1) ?? '-' }}</el-descriptions-item>
      <el-descriptions-item label="T4 思考效率">{{ score.t4_thinking?.toFixed(1) ?? '-' }}</el-descriptions-item>
      <el-descriptions-item label="E 端到端性能">{{ score.e_performance?.toFixed(1) ?? '-' }}</el-descriptions-item>
      <el-descriptions-item label="C 成本效率">{{ score.c_cost?.toFixed(1) ?? '-' }}</el-descriptions-item>
      <el-descriptions-item label="总分" :span="2">
        <el-tag :type="score.overall_score >= 80 ? 'success' : score.overall_score >= 60 ? 'warning' : 'danger'" size="large">
          {{ score.overall_score?.toFixed(1) ?? '-' }}
        </el-tag>
      </el-descriptions-item>
    </el-descriptions>

    <!-- Actual Metrics -->
    <el-card header="实际执行指标" style="margin-top: 16px;" v-if="score">
      <el-row :gutter="12">
        <el-col :span="8"><el-statistic title="工具调用次数" :value="score.actual_tool_calls ?? 0" /></el-col>
        <el-col :span="8"><el-statistic title="成功次数" :value="score.actual_success_calls ?? 0" /></el-col>
        <el-col :span="8"><el-statistic title="Token 消耗" :value="score.actual_tokens ?? 0" /></el-col>
        <el-col :span="8"><el-statistic title="思考轮次" :value="score.actual_rounds ?? 0" /></el-col>
        <el-col :span="8"><el-statistic title="耗时 (ms)" :value="score.actual_time_ms ?? 0" /></el-col>
        <el-col :span="8"><el-statistic title="成本 (USD)" :value="score.actual_cost_usd ?? 0" :precision="4" /></el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { scoresApi } from '../api'
import { ElMessage } from 'element-plus'

const props = defineProps<{ runId: string; questionId: string }>()

const loading = ref(false)
const score = ref<any>(null)

async function load() {
  if (!props.runId || !props.questionId) return
  loading.value = true
  try {
    const res = await scoresApi.get(props.runId, props.questionId)
    score.value = res.data
  } catch (e: any) {
    ElMessage.error('加载详情失败')
  } finally {
    loading.value = false
  }
}

watch(() => [props.runId, props.questionId], load, { immediate: true })
</script>
