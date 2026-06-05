<template>
  <div>
    <el-page-header @back="$router.push('/')" title="返回">
      <template #content>
        <span style="font-size: 18px;">共性分析 — {{ runId }}</span>
      </template>
    </el-page-header>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- Pass Rate Card -->
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>通过率 (pass@k / pass^k)</template>
          <div v-if="passRate">
            <el-row :gutter="12">
              <el-col :span="12">
                <el-statistic title="pass@k" :value="passRate.pass_at_k_pct" suffix="%">
                  <template #prefix>{{ passRate.pass_at_k }} / {{ passRate.total_questions }}</template>
                </el-statistic>
              </el-col>
              <el-col :span="12">
                <el-statistic title="pass^k" :value="passRate.pass_power_k_pct" suffix="%">
                  <template #prefix>{{ passRate.pass_power_k }} / {{ passRate.total_questions }}</template>
                </el-statistic>
              </el-col>
            </el-row>
            <div style="margin-top: 12px; text-align: center;">
              <el-tag :type="ppGapType">{{ ppGapText }}</el-tag>
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>

      <!-- Common Issues -->
      <el-col :span="16">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>共性问题</span>
              <el-button type="primary" size="small" @click="extract" :loading="extracting">
                提取共性分析
              </el-button>
            </div>
          </template>

          <div v-if="commonIssues.length > 0">
            <el-timeline>
              <el-timeline-item
                v-for="(issue, idx) in commonIssues"
                :key="idx"
                :timestamp="issue.dimension"
                placement="top"
                :color="issueColor(issue.dimension)"
              >
                <el-card shadow="hover">
                  <p><strong>{{ issue.issue }}</strong></p>
                  <p style="color: #666; font-size: 13px;">频次: {{ issue.frequency }} | 影响: {{ issue.impact }}</p>
                  <div v-if="issue.examples?.length" style="margin-top: 8px;">
                    <el-tag v-for="(ex, i) in issue.examples" :key="i" size="small" style="margin: 2px;">
                      {{ ex.substring(0, 60) }}{{ ex.length > 60 ? '...' : '' }}
                    </el-tag>
                  </div>
                </el-card>
              </el-timeline-item>
            </el-timeline>
          </div>
          <el-empty v-else description="尚未提取共性分析" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Improvement Suggestions -->
    <el-card style="margin-top: 20px;" v-if="improvements.length > 0">
      <template #header><span>改进建议</span></template>
      <el-table :data="improvements" stripe>
        <el-table-column prop="type" label="类型" width="150">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="row.priority === '高' ? 'danger' : row.priority === '中' ? 'warning' : 'info'" size="small">
              {{ row.priority }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="suggestion" label="建议内容" />
        <el-table-column prop="expected_impact" label="预期效果" width="200" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { metaApi } from '../api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const runId = computed(() => route.params.runId as string)

const passRate = ref<any>(null)
const commonIssues = ref<any[]>([])
const improvements = ref<any[]>([])
const extracting = ref(false)

const ppGapText = computed(() => {
  if (!passRate.value) return ''
  const gap = passRate.value.pp_gap
  return `PP 差值: ${gap}% — ${gap > 20 ? '能力不稳定，需优化' : gap > 10 ? '略有波动' : '表现稳定'}`
})

const ppGapType = computed(() => {
  if (!passRate.value) return 'info'
  return passRate.value.pp_gap > 20 ? 'danger' : passRate.value.pp_gap > 10 ? 'warning' : 'success'
})

function issueColor(dim: string): string {
  const map: Record<string, string> = {
    '执行效率': '#e6a23c',
    '工具准确性': '#409eff',
    '思考效率': '#67c23a',
    '任务完成度': '#f56c6c',
  }
  return map[dim] || '#909399'
}

async function loadPassRate() {
  try {
    const res = await metaApi.passRate(runId.value)
    passRate.value = res.data
  } catch {}
}

async function loadCommonIssues() {
  try {
    const res = await metaApi.commonIssues(runId.value)
    if (res.data.common_issues) {
      commonIssues.value = res.data.common_issues
      improvements.value = res.data.improvement_suggestions || []
    }
  } catch {}
}

async function extract() {
  extracting.value = true
  try {
    await metaApi.extract(runId.value)
    ElMessage.success('共性分析已触发，请稍后刷新查看结果')
    setTimeout(() => loadCommonIssues(), 3000)
  } catch (e: any) {
    ElMessage.error('提取失败: ' + (e.message || ''))
  } finally {
    extracting.value = false
  }
}

onMounted(() => {
  loadPassRate()
  loadCommonIssues()
})
</script>
