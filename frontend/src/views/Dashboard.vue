<template>
  <div>
    <h1>📊 CoworkEval 评测平台</h1>

    <!-- Step 1: Manifest -->
    <el-card style="margin-bottom: 16px;">
      <template #header><b>① 评测集</b></template>
      <el-row :gutter="12" align="middle">
        <el-col :span="12">
          <el-select v-model="form.benchmark_id" placeholder="选择评测集" @change="onBenchmarkChange" style="width:100%" :loading="loading.manifests" clearable>
            <el-option v-for="m in manifests" :key="m.benchmark_id" :label="`${m.benchmark_id} (${m.total_questions}题 v${m.version})`" :value="m.benchmark_id" />
          </el-select>
        </el-col>
        <el-col :span="12">
          <input type="file" accept=".json" @change="handleManifestUpload" ref="mfRef" style="display:none" />
          <el-button @click="($refs.mfRef as any)?.click()" :loading="loading.uploadManifest">上传新 Manifest JSON</el-button>
          <span v-if="uploadMsg" style="margin-left:8px;color:#67c23a;">{{ uploadMsg }}</span>
          <span v-if="error.manifests" style="color:#f56c6c;margin-left:8px;">{{ error.manifests }}</span>
        </el-col>
      </el-row>
    </el-card>

    <!-- Step 2: Question -->
    <el-card style="margin-bottom:16px;">
      <template #header><b>② 题目</b> <span style="color:#999;font-weight:400;">(需先选评测集)</span></template>
      <el-select v-model="form.question_id" placeholder="选择题号" style="width:100%;" :disabled="!form.benchmark_id">
        <el-option v-for="q in questions" :key="q.question_id"
          :label="`${q.question_id} — ${q.question_name} [${q.difficulty}] Skill: ${q.skills || '无'}`"
          :value="q.question_id" />
      </el-select>
      <div v-if="selectedQuestion" style="margin-top:8px;font-size:12px;color:#999;">
        Baseline: {{ selectedQuestion.baseline_tool_count }}工具 {{ selectedQuestion.baseline_tokens }}tokens
        {{ selectedQuestion.baseline_time_ms }}ms ${{ selectedQuestion.baseline_cost_usd }}
      </div>
    </el-card>

    <!-- Step 3: Trace -->
    <el-card style="margin-bottom:16px;">
      <template #header><b>③ Trace 文件</b> <span style="color:#999;font-weight:400;">(.jsonl 格式)</span></template>
      <input type="file" accept=".jsonl" @change="(e:any)=>{form.traceFile=e.target?.files?.[0]||null; form.traceName=e.target?.files?.[0]?.name||''}" ref="trRef" style="display:none" />
      <el-row :gutter="12" align="middle">
        <el-col :span="8">
          <el-button @click="($refs.trRef as any)?.click()">选择 .jsonl 文件</el-button>
        </el-col>
        <el-col :span="16">
          <el-tag v-if="form.traceName" type="success">{{ form.traceName }}</el-tag>
          <span v-else style="color:#999;">未选择</span>
        </el-col>
      </el-row>
    </el-card>

    <!-- Step 4: Run -->
    <el-card style="margin-bottom:16px;background:#f0f9ff;">
      <el-row align="middle">
        <el-col :span="12">
          <el-button type="primary" size="large" @click="runEval" :loading="running" :disabled="!canRun">
            🚀 开始评测
          </el-button>
          <el-checkbox v-model="form.useJudge" style="margin-left:12px;">启用裁判模型 (DeepSeek)</el-checkbox>
        </el-col>
        <el-col :span="12" style="text-align:right;">
          <span v-if="error.eval" style="color:#f56c6c;">{{ error.eval }}</span>
        </el-col>
      </el-row>
    </el-card>

    <!-- Result -->
    <el-card v-if="lastResult" style="border:2px solid #409eff;margin-bottom:16px;">
      <template #header>
        <b>📋 {{ lastResult.question_name || lastResult.question_id }}</b>
        <el-tag size="small" style="margin-left:8px;" type="info">{{ lastResult.difficulty }}</el-tag>
        <el-tag size="small" style="margin-left:4px;" v-if="lastResult.skills">Skill: {{ lastResult.skills }}</el-tag>
      </template>

      <!-- Baseline vs Actual -->
      <el-table :data="compareRows" size="small" border>
        <el-table-column prop="metric" label="指标" width="120" />
        <el-table-column prop="baseline" label="Baseline (基准)" width="150" />
        <el-table-column prop="actual" label="实际" width="150" />
        <el-table-column prop="delta" label="偏差" width="100">
          <template #default="{row}"><span :style="{color:row.bad?'#f56c6c':'#67c23a'}">{{ row.delta }}</span></template>
        </el-table-column>
      </el-table>

      <el-divider />
      <!-- TTTEC Scores -->
      <el-row :gutter="12">
        <el-col :span="4" v-for="d in scoreDims" :key="d.key">
          <div style="text-align:center;padding:8px;">
            <div style="font-size:26px;font-weight:bold;" :style="{color:d.color}">{{ d.val }}</div>
            <div style="font-size:11px;color:#999;">{{ d.label }}</div>
          </div>
        </el-col>
      </el-row>

      <!-- Judge Result -->
      <el-divider v-if="lastResult.judge && !lastResult.judge.error" />
      <div v-if="lastResult.judge && !lastResult.judge.error">
        <div style="font-weight:bold;margin-bottom:8px;">🧠 Judge 裁判模型评分 (DeepSeek)</div>
        <el-row :gutter="12">
          <el-col :span="6" v-for="jd in judgeDims" :key="jd.key">
            <el-card shadow="hover" :body-style="{padding:'8px',textAlign:'center'}">
              <div style="font-size:22px;font-weight:bold;" :style="{color:jd.color}">{{ jd.val }}</div>
              <div style="font-size:10px;color:#999;">{{ jd.label }}</div>
            </el-card>
          </el-col>
        </el-row>
        <div style="margin-top:8px;color:#666;font-size:13px;" v-if="lastResult.judge.conclusion">
          💬 {{ lastResult.judge.conclusion?.substring(0, 200) }}
        </div>
        <div v-if="lastResult.judge.skill_compliance" style="margin-top:4px;font-size:12px;color:#999;">
          Skill合规: {{ lastResult.judge.skill_compliance.score }}/100
        </div>
      </div>
      <div v-if="lastResult.judge?.error" style="color:#f56c6c;font-size:12px;">
        ⚠️ Judge 调用失败: {{ lastResult.judge.error }}
      </div>

      <el-button type="primary" size="small" style="margin-top:12px;" @click="$router.push(`/runs/${lastResult.run_id}`)">
        查看版本详情 →
      </el-button>
    </el-card>

    <!-- History -->
    <el-card>
      <template #header><b>📋 评测历史</b></template>
      <el-table :data="runs" empty-text="暂无评测记录" size="small" max-height="300">
        <el-table-column label="Run" width="100">
          <template #default="{row}">
            <el-link type="primary" @click="$router.push(`/runs/${row.id}`)">{{ row.id?.substring(0,8) }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="benchmark_id" label="评测集" width="180" />
        <el-table-column label="状态" width="100">
          <template #default="{row}">
            <el-tag :type="row.status==='COMPLETED'?'success':row.status==='FAILED'?'danger':'warning'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{row}">{{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{row}">
            <el-button size="small" type="danger" @click="deleteRun(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

const API = '/coworkeval/v1'

const manifests = ref<any[]>([])
const questions = ref<any[]>([])
const runs = ref<any[]>([])
const lastResult = ref<any>(null)
const running = ref(false)
const uploadMsg = ref('')

const loading = reactive({ manifests: false, uploadManifest: false })
const error = reactive({ manifests: '', eval: '' })

const form = reactive({
  benchmark_id: '',
  question_id: '',
  traceFile: null as File | null,
  traceName: '',
  useJudge: false,
})

const canRun = computed(() => form.benchmark_id && form.question_id && form.traceFile)

const selectedQuestion = computed(() => questions.value.find((q:any) => q.question_id === form.question_id))

const compareRows = computed(() => {
  if (!lastResult.value) return []
  const b = lastResult.value.baseline || {}
  const a = lastResult.value.actual || {}
  const fmt = (v: any) => typeof v === 'number' ? v.toLocaleString() : String(v??'-')
  const pct = (bv: number, av: number) => bv ? `${((av-bv)/bv*100).toFixed(0)}%` : '-'
  return [
    {metric:'工具调用',baseline:fmt(b.tool_count),actual:fmt(a.tool_calls),
     delta:pct(b.tool_count,a.tool_calls),bad:(a.tool_calls??0)>(b.tool_count??0)},
    {metric:'Token',baseline:fmt(b.tokens),actual:fmt(a.tokens),
     delta:pct(b.tokens,a.tokens),bad:(a.tokens??0)>(b.tokens??0)},
    {metric:'轮次',baseline:fmt(b.rounds),actual:fmt(a.rounds),
     delta:pct(b.rounds,a.rounds),bad:(a.rounds??0)>(b.rounds??0)},
    {metric:'耗时',baseline:fmt(b.time_ms)+'ms',actual:fmt(a.duration_ms)+'ms',
     delta:pct(b.time_ms,a.duration_ms),bad:(a.duration_ms??0)>(b.time_ms??0)},
    {metric:'成本',baseline:'$'+fmt(b.cost_usd),actual:'$'+fmt(a.cost_usd),
     delta:pct(b.cost_usd,a.cost_usd),bad:(a.cost_usd??0)>(b.cost_usd??0)},
  ]
})

const judgeDims = computed(() => {
  if (!lastResult.value?.judge) return []
  const j = lastResult.value.judge
  if (j.error) return []
  return [
    {key:'eff',label:'执行效率',val:j.execution_efficiency,color:'#e6a23c'},
    {key:'tool',label:'工具准确性',val:j.tool_accuracy,color:'#409eff'},
    {key:'think',label:'思考效率',val:j.thinking_efficiency,color:'#67c23a'},
    {key:'task',label:'任务完成度',val:j.task_completion,color:'#f56c6c'},
  ]
})

const scoreDims = computed(() => {
  if (!lastResult.value?.scores) return []
  const s = lastResult.value.scores
  return [
    {key:'t1',label:'T1 完成度',val:s.t1_completion?.toFixed(1)??'-',color:'#409eff'},
    {key:'t2',label:'T2 准确率',val:s.t2_accuracy?.toFixed(1)??'-',color:'#67c23a'},
    {key:'t3',label:'T3 效率',val:s.t3_efficiency?.toFixed(1)??'-',color:'#e6a23c'},
    {key:'t4',label:'T4 思考',val:s.t4_thinking?.toFixed(1)??'-',color:'#f56c6c'},
    {key:'e',label:'E 性能',val:s.e_performance?.toFixed(1)??'-',color:'#909399'},
    {key:'c',label:'C 成本',val:s.c_cost?.toFixed(1)??'-',color:'#b37feb'},
  ]
})

function onBenchmarkChange(bid: string) {
  const m = manifests.value.find((x:any) => x.benchmark_id === bid)
  questions.value = m?.questions || []
  form.question_id = ''
}

async function loadData() {
  loading.manifests = true
  error.manifests = ''
  try {
    const [mRes, rRes] = await Promise.all([
      axios.get(`${API}/manifests`),
      axios.get(`${API}/runs`),
    ])
    manifests.value = mRes.data || []
    runs.value = rRes.data || []
    if (manifests.value.length && !form.benchmark_id) {
      form.benchmark_id = manifests.value[0].benchmark_id
      onBenchmarkChange(form.benchmark_id)
    }
  } catch (e: any) {
    error.manifests = `加载失败: ${e.message}`
    console.error(e)
  } finally {
    loading.manifests = false
  }
}

async function handleManifestUpload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  loading.uploadManifest = true
  uploadMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await axios.post(`${API}/manifests/upload`, fd)
    uploadMsg.value = `✅ 已注册: ${res.data.benchmark_id}`
    ElMessage.success(`评测集 ${res.data.benchmark_id} 已注册`)
    await loadData()
    form.benchmark_id = res.data.benchmark_id
    onBenchmarkChange(res.data.benchmark_id)
  } catch (e: any) {
    uploadMsg.value = ''
    ElMessage.error('上传失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.uploadManifest = false
  }
}

async function runEval() {
  if (!canRun.value) return
  running.value = true
  error.eval = ''
  lastResult.value = null
  try {
    const fd = new FormData()
    fd.append('benchmark_id', form.benchmark_id)
    fd.append('question_id', form.question_id)
    fd.append('trace_file', form.traceFile!)
    fd.append('judge_enabled', String(form.useJudge))
    const res = await axios.post(`${API}/runs/evaluate`, fd)
    lastResult.value = res.data
    ElMessage.success(`评测完成! Overall: ${res.data.scores.overall_score?.toFixed(1)}`)
    await loadData()
  } catch (e: any) {
    error.eval = `评测失败: ${e.response?.data?.detail || e.message}`
    ElMessage.error(error.eval)
  } finally {
    running.value = false
  }
}

async function deleteRun(runId: string) {
  try {
    await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' })
    await axios.delete(`${API}/runs/${runId}`)
    ElMessage.success('已删除')
    await loadData()
  } catch {}
}

onMounted(loadData)
</script>
