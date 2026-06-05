<template>
  <div>
    <el-button @click="goBack" style="margin-bottom:12px;" icon="ArrowLeft">返回 Dashboard</el-button>
    <h2>🔍 共性分析 — {{ runId }}</h2>
    <el-row :gutter="20" style="margin-top:16px;">
      <el-col :span="8">
        <el-card header="通过率">
          <div v-if="passRate">
            <el-statistic title="pass@k" :value="passRate.pass_at_k_pct" suffix="%" />
            <el-statistic title="pass^k" :value="passRate.pass_power_k_pct" suffix="%" style="margin-top:12px;"/>
            <el-tag style="margin-top:8px;" :type="passRate.pp_gap>20?'danger':'success'">PP 差值: {{ passRate.pp_gap }}%</el-tag>
          </div>
          <el-empty v-else description="暂无" />
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card header="共性问题">
          <div v-if="issues.length">
            <el-timeline>
              <el-timeline-item v-for="(iss, i) in issues" :key="i" :timestamp="iss.dimension">
                <p><strong>{{ iss.issue }}</strong></p>
                <p style="color:#999;font-size:12px;">频次: {{ iss.frequency }} | 影响: {{ iss.impact }}</p>
              </el-timeline-item>
            </el-timeline>
          </div>
          <el-empty v-else description="暂无共性分析" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const API='/coworkeval/v1'
const route = useRoute()
const router = useRouter()
const runId = computed(() => route.params.runId as string)
const passRate = ref<any>(null)
const issues = ref<any[]>([])

function goBack() { router.push({name:'dashboard'}).catch(()=>{window.location.href='/'}) }

onMounted(async() => {
  try { const r = await axios.get(`${API}/meta/${runId.value}/pass-rate`); passRate.value = r.data } catch(e) { console.error(e) }
  try { const r = await axios.get(`${API}/meta/${runId.value}/common-issues`); issues.value = r.data.common_issues||[] } catch(e) { console.error(e) }
})
</script>
