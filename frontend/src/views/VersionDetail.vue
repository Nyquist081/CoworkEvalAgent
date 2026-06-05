<template>
  <div>
    <el-button @click="goBack" style="margin-bottom:12px;" icon="ArrowLeft">返回 Dashboard</el-button>
    <h2>📋 版本详情 — {{ runId }}</h2>

    <el-row :gutter="16" style="margin:16px 0;" v-if="scores.length">
      <el-col :span="4" v-for="d in avgDims" :key="d.key">
        <el-card shadow="hover" :body-style="{padding:'12px',textAlign:'center'}">
          <div style="font-size:24px;font-weight:bold;" :style="{color:d.color}">{{ d.val }}</div>
          <div style="font-size:11px;color:#999;">{{ d.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>题目评分 ({{ scores.length }})</template>
      <el-table :data="scores" stripe @row-click="showDetail" style="cursor:pointer;">
        <el-table-column prop="question_id" label="题目" width="200" />
        <el-table-column label="T1" width="55"><template #default="{r}">{{ r.t1_completion?.toFixed(0)??'-' }}</template></el-table-column>
        <el-table-column label="T2" width="55"><template #default="{r}">{{ r.t2_accuracy?.toFixed(0)??'-' }}</template></el-table-column>
        <el-table-column label="T3" width="55"><template #default="{r}">{{ r.t3_efficiency?.toFixed(0)??'-' }}</template></el-table-column>
        <el-table-column label="T4" width="55"><template #default="{r}">{{ r.t4_thinking?.toFixed(0)??'-' }}</template></el-table-column>
        <el-table-column label="E" width="55"><template #default="{r}">{{ r.e_performance?.toFixed(0)??'-' }}</template></el-table-column>
        <el-table-column label="C" width="55"><template #default="{r}">{{ r.c_cost?.toFixed(0)??'-' }}</template></el-table-column>
        <el-table-column label="总分" width="80">
          <template #default="{r}">
            <el-tag :type="(r.overall_score??0)>=80?'success':(r.overall_score??0)>=60?'warning':'danger'" size="small">
              {{ r.overall_score?.toFixed(1)??'-' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialog" :title="'题目: '+selectedQid" width="650px">
      <el-descriptions :column="2" border v-if="detail">
        <el-descriptions-item label="T1 完成度">{{ detail.t1_completion?.toFixed(1)??'-' }}</el-descriptions-item>
        <el-descriptions-item label="T2 准确率">{{ detail.t2_accuracy?.toFixed(1)??'-' }}</el-descriptions-item>
        <el-descriptions-item label="T3 效率">{{ detail.t3_efficiency?.toFixed(1)??'-' }}</el-descriptions-item>
        <el-descriptions-item label="T4 思考">{{ detail.t4_thinking?.toFixed(1)??'-' }}</el-descriptions-item>
        <el-descriptions-item label="E 性能">{{ detail.e_performance?.toFixed(1)??'-' }}</el-descriptions-item>
        <el-descriptions-item label="C 成本">{{ detail.c_cost?.toFixed(1)??'-' }}</el-descriptions-item>
        <el-descriptions-item label="总分" :span="2">
          <el-tag :type="(detail.overall_score??0)>=80?'success':(detail.overall_score??0)>=60?'warning':'danger'" size="large">
            {{ detail.overall_score?.toFixed(1)??'-' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <el-divider />
      <el-row :gutter="12" v-if="detail">
        <el-col :span="8"><el-statistic title="工具调用" :value="detail.actual_tool_calls" /></el-col>
        <el-col :span="8"><el-statistic title="Token" :value="detail.actual_tokens" /></el-col>
        <el-col :span="8"><el-statistic title="耗时ms" :value="detail.actual_time_ms" /></el-col>
        <el-col :span="8"><el-statistic title="轮次" :value="detail.actual_rounds" /></el-col>
        <el-col :span="8"><el-statistic title="成功" :value="detail.actual_success_calls" /></el-col>
        <el-col :span="8"><el-statistic title="成本$" :value="detail.actual_cost_usd" :precision="4" /></el-col>
      </el-row>
    </el-dialog>
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
const scores = ref<any[]>([])
const dialog = ref(false)
const selectedQid = ref('')
const detail = ref<any>(null)

const avgDims = computed(() => {
  if(!scores.value.length) return []
  const a = (k:string) => (scores.value.reduce((t:number,s:any)=>t+(s[k]??0),0)/scores.value.length).toFixed(1)
  return [
    {key:'t1',label:'T1 完成度',val:a('t1_completion'),color:'#409eff'},
    {key:'t2',label:'T2 准确率',val:a('t2_accuracy'),color:'#67c23a'},
    {key:'t3',label:'T3 效率',val:a('t3_efficiency'),color:'#e6a23c'},
    {key:'t4',label:'T4 思考',val:a('t4_thinking'),color:'#f56c6c'},
    {key:'e',label:'E 性能',val:a('e_performance'),color:'#909399'},
    {key:'c',label:'C 成本',val:a('c_cost'),color:'#b37feb'},
  ]
})

function goBack() { router.push('/') }

async function load() {
  try { const r = await axios.get(`${API}/runs/${runId.value}/scores`); scores.value = r.data||[] }
  catch(e) { console.error(e) }
}

async function showDetail(row: any) {
  selectedQid.value = row.question_id; dialog.value = true
  try { const r = await axios.get(`${API}/runs/${runId.value}/scores/${row.question_id}`); detail.value = r.data }
  catch { detail.value = row }
}

onMounted(load)
</script>
