<template>
  <div>
    <h1>📊 CoworkEval 评测平台</h1>

    <el-row :gutter="20">
      <!-- Left: New Evaluation -->
      <el-col :span="12">
        <el-card header="🚀 新建评测任务" style="margin-bottom: 20px;">
          <el-form label-width="80px">
            <el-form-item label="评测集">
              <el-select v-model="form.benchmark_id" placeholder="选择已有评测集" @change="loadQuestions" style="width: 100%;">
                <el-option v-for="m in allManifests" :key="m.benchmark_id" :label="m.benchmark_id" :value="m.benchmark_id" />
              </el-select>
              <el-divider style="margin: 8px 0;" />
              <input type="file" accept=".json" @change="uploadManifest" ref="manifestInput" style="display:none" />
              <el-button size="small" @click="($refs.manifestInput as any)?.click()">或上传新的 Manifest JSON</el-button>
              <span v-if="uploadMsg" style="margin-left: 8px; color: #67c23a;">{{ uploadMsg }}</span>
            </el-form-item>

            <el-form-item label="题目">
              <el-select v-model="form.question_id" placeholder="选择题号" style="width: 100%;">
                <el-option v-for="q in currentQuestions" :key="q.question_id"
                  :label="`${q.question_id}: ${q.question_name} [${q.difficulty}]`" :value="q.question_id" />
              </el-select>
            </el-form-item>

            <el-form-item label="Trace">
              <input type="file" accept=".jsonl" @change="(e: any) => form.traceFile = e.target?.files?.[0]" />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="runEval" :loading="running" :disabled="!canRun">
                🚀 开始评测
              </el-button>
              <el-checkbox v-model="form.useJudge" style="margin-left: 12px;">启用裁判模型</el-checkbox>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- Result -->
        <el-card v-if="lastResult" header="📋 最新评测结果" style="border: 2px solid #409eff;">
          <div v-if="lastResult.question_id">
            <el-row :gutter="12">
              <el-col :span="4" v-for="d in scoreDims" :key="d.key">
                <div style="text-align: center;">
                  <div style="font-size: 22px; font-weight: bold;" :style="{color: d.color}">{{ d.val }}</div>
                  <div style="font-size: 11px; color: #999;">{{ d.label }}</div>
                </div>
              </el-col>
            </el-row>
            <el-divider />
            <el-descriptions :column="3" size="small">
              <el-descriptions-item label="工具调用">{{ lastResult.metrics?.tool_calls }}</el-descriptions-item>
              <el-descriptions-item label="Token">{{ lastResult.metrics?.tokens?.toLocaleString() }}</el-descriptions-item>
              <el-descriptions-item label="耗时">{{ lastResult.metrics?.duration_ms }}ms</el-descriptions-item>
              <el-descriptions-item label="成功">{{ lastResult.metrics?.success_calls }}</el-descriptions-item>
              <el-descriptions-item label="轮次">{{ lastResult.metrics?.rounds }}</el-descriptions-item>
              <el-descriptions-item label="成本">${{ lastResult.metrics?.cost_usd }}</el-descriptions-item>
            </el-descriptions>
            <el-button type="primary" size="small" @click="$router.push(`/runs/${lastResult.run_id}`)" style="margin-top: 8px;">
              查看详情 →
            </el-button>
          </div>
        </el-card>
      </el-col>

      <!-- Right: Runs History -->
      <el-col :span="12">
        <el-card header="📋 评测历史" style="margin-bottom: 20px;">
          <el-table :data="runs" empty-text="暂无评测记录" size="small" max-height="400">
            <el-table-column label="Run" width="100">
              <template #default="{ row }">
                <el-link type="primary" @click="$router.push(`/runs/${row.id}`)">{{ row.id?.substring(0, 8) }}</el-link>
              </template>
            </el-table-column>
            <el-table-column prop="benchmark_id" label="评测集" width="160" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status==='COMPLETED'?'success':row.status==='FAILED'?'danger':'warning'" size="small">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="时间" width="150">
              <template #default="{ row }">{{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '' }}</template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- Quick stats -->
        <el-card header="📈 评测集概览">
          <el-table :data="allManifests" size="small" empty-text="暂无评测集">
            <el-table-column prop="benchmark_id" label="ID" />
            <el-table-column prop="total_questions" label="题目数" width="80" />
            <el-table-column prop="version" label="版本" width="80" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const API = 'http://localhost:8000/coworkeval/v1'

const running = ref(false)
const allManifests = ref<any[]>([])
const currentQuestions = ref<any[]>([])
const runs = ref<any[]>([])
const lastResult = ref<any>(null)
const uploadMsg = ref('')

const form = reactive({
  benchmark_id: '',
  question_id: '',
  traceFile: null as File | null,
  useJudge: false,
})

const canRun = computed(() => form.benchmark_id && form.question_id && form.traceFile)

const scoreDims = computed(() => {
  if (!lastResult.value?.scores) return []
  const s = lastResult.value.scores
  return [
    { key:'t1',label:'T1 完成度',val:s.t1_completion?.toFixed(1)??'-',color:'#409eff'},
    { key:'t2',label:'T2 准确率',val:s.t2_accuracy?.toFixed(1)??'-',color:'#67c23a'},
    { key:'t3',label:'T3 效率',val:s.t3_efficiency?.toFixed(1)??'-',color:'#e6a23c'},
    { key:'t4',label:'T4 思考',val:s.t4_thinking?.toFixed(1)??'-',color:'#f56c6c'},
    { key:'e',label:'E 性能',val:s.e_performance?.toFixed(1)??'-',color:'#909399'},
    { key:'c',label:'C 成本',val:s.c_cost?.toFixed(1)??'-',color:'#b37feb'},
  ]
})

async function loadData() {
  try {
    const [mRes, rRes] = await Promise.all([
      axios.get(`${API}/manifests`),
      axios.get(`${API}/runs`),
    ])
    allManifests.value = mRes.data || []
    runs.value = rRes.data || []
  } catch (e: any) {
    console.error('Load error:', e.message)
  }
}

function loadQuestions(bid: string) {
  const m = allManifests.value.find((x: any) => x.benchmark_id === bid)
  currentQuestions.value = m?.questions || []
}

async function uploadManifest(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const fd = new FormData()
  fd.append('file', file)
  try {
    const res = await axios.post(`${API}/manifests/upload`, fd)
    uploadMsg.value = `已注册: ${res.data.benchmark_id}`
    await loadData()
  } catch (err: any) {
    uploadMsg.value = '上传失败'
  }
}

async function runEval() {
  if (!canRun.value) return
  running.value = true
  lastResult.value = null
  try {
    const fd = new FormData()
    fd.append('benchmark_id', form.benchmark_id)
    fd.append('question_id', form.question_id)
    fd.append('trace_file', form.traceFile!)
    fd.append('judge_enabled', String(form.useJudge))
    const res = await axios.post(`${API}/runs/evaluate`, fd)
    lastResult.value = res.data
    ElMessage.success('评测完成！')
    await loadData()
  } catch (e: any) {
    ElMessage.error('评测失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    running.value = false
  }
}

onMounted(loadData)
</script>
