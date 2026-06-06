<template>
  <div class="dashboard-shell">
    <section class="dashboard-hero">
      <div>
        <p class="eyebrow">CoworkEval Platform</p>
        <h1>工业 Agent 离线评测操作台</h1>
        <p class="hero-copy">从标准 run bundle 启动评测，沉淀版本、模型、Trace 质量和多维评分。</p>
      </div>
      <div class="hero-metrics">
        <div>
          <span>{{ runs.length }}</span>
          <small>历史运行</small>
        </div>
        <div>
          <span>{{ completedRuns }}</span>
          <small>已完成</small>
        </div>
        <div>
          <span>{{ latestRunLabel }}</span>
          <small>最近版本</small>
        </div>
      </div>
    </section>

    <section class="workspace-grid">
      <el-card class="run-panel" shadow="never">
        <template #header>
          <div class="card-title">
            <b>新建评测</b>
            <el-radio-group v-model="form.mode" size="small">
              <el-radio-button label="offline">离线 Run Bundle</el-radio-button>
              <el-radio-button label="single">单 Trace 调试</el-radio-button>
            </el-radio-group>
          </div>
        </template>

        <div v-if="form.mode === 'offline'" class="form-stack">
          <el-input v-model="form.benchmarkRoot" placeholder="../evaluations/industrial-demo">
            <template #prepend>benchmark_root</template>
          </el-input>
          <el-input v-model="form.runLabel" placeholder="alarm-with-skill">
            <template #prepend>run_label</template>
          </el-input>
          <div class="quick-row">
            <el-button size="small" @click="useDemoBundle">使用 Demo</el-button>
            <el-tag type="info" effect="plain">runs/{{ form.runLabel || '{label}' }}/{{ previewQuestion }}/attempt-1</el-tag>
          </div>
        </div>

    <!-- Step 1: Manifest -->
        <div v-if="form.mode === 'single'" class="form-stack">
          <el-select v-model="form.benchmark_id" placeholder="选择评测集" @change="onBenchmarkChange" style="width:100%" :loading="loading.manifests" clearable>
            <el-option v-for="m in manifests" :key="m.benchmark_id" :label="`${m.benchmark_id} (${m.total_questions}题 v${m.version})`" :value="m.benchmark_id" />
          </el-select>
          <el-select v-model="form.question_id" placeholder="选择题号" style="width:100%;" :disabled="!form.benchmark_id">
            <el-option v-for="q in questions" :key="q.question_id"
              :label="`${q.question_id} — ${q.question_name} [${q.difficulty}] Skill: ${q.skills || '无'}`"
              :value="q.question_id" />
          </el-select>
          <input type="file" accept=".json" @change="handleManifestUpload" ref="mfRef" style="display:none" />
          <input type="file" accept=".jsonl" @change="(e:any)=>{form.traceFile=e.target?.files?.[0]||null; form.traceName=e.target?.files?.[0]?.name||''}" ref="trRef" style="display:none" />
          <div class="quick-row">
            <el-button @click="($refs.trRef as any)?.click()">选择 .jsonl 文件</el-button>
            <el-button @click="($refs.mfRef as any)?.click()" :loading="loading.uploadManifest">上传 Manifest</el-button>
          </div>
          <el-tag v-if="form.traceName" type="success">{{ form.traceName }}</el-tag>
          <div v-if="selectedQuestion" class="muted-line">
            Baseline: {{ selectedQuestion.baseline_tool_count }} 工具 / {{ selectedQuestion.baseline_tokens }} tokens / {{ selectedQuestion.baseline_time_ms }} ms
          </div>
        </div>

        <div class="run-actions">
          <el-checkbox v-model="form.useJudge">启用 Judge (DeepSeek)</el-checkbox>
          <el-button type="primary" size="large" @click="runEval" :loading="running" :disabled="!canRun">
            开始评测
          </el-button>
        </div>
        <el-alert v-if="error.eval" :title="error.eval" type="error" :closable="false" show-icon />
        <el-alert v-if="uploadMsg" :title="uploadMsg" type="success" :closable="false" show-icon />
        <el-alert v-if="error.manifests" :title="error.manifests" type="warning" :closable="false" show-icon />
      </el-card>

      <el-card class="run-panel" shadow="never">
        <template #header><b>目录预检</b></template>
        <div class="check-list">
          <div v-for="item in directoryChecks" :key="item.label" class="check-item">
            <el-icon :class="item.ok ? 'ok' : 'pending'"><CircleCheckFilled /></el-icon>
            <div>
              <b>{{ item.label }}</b>
              <span>{{ item.value }}</span>
            </div>
          </div>
        </div>
        <el-divider />
        <el-steps :active="stepActive" finish-status="success" align-center>
          <el-step title="目录" />
          <el-step title="Trace" />
          <el-step title="评分" />
          <el-step title="完成" />
        </el-steps>
      </el-card>
    </section>

    <!-- Result -->
    <el-card v-if="lastResult" class="result-card" shadow="never">
      <template #header>
        <b>📋 {{ lastResult.run_label || lastResult.question_name || lastResult.question_id }}</b>
        <el-tag size="small" style="margin-left:8px;" type="info">{{ lastResult.difficulty }}</el-tag>
        <el-tag size="small" style="margin-left:4px;" v-if="lastResult.skills">Skill: {{ lastResult.skills }}</el-tag>
        <el-tag size="small" style="margin-left:4px;" v-if="lastResult.score_count != null">Scores: {{ lastResult.score_count }}</el-tag>
      </template>

      <div v-if="lastResult.score_count != null" class="offline-summary">
        <div>
          <span>Run ID</span>
          <b>{{ lastResult.run_id?.substring(0, 8) }}</b>
        </div>
        <div>
          <span>Benchmark</span>
          <b>{{ lastResult.benchmark_id }}</b>
        </div>
        <div>
          <span>Scores</span>
          <b>{{ lastResult.score_count }}</b>
        </div>
        <div>
          <span>Judge</span>
          <b>{{ lastResult.judge_enabled ? 'enabled' : 'disabled' }}</b>
        </div>
      </div>

      <!-- T1 Comparison -->
      <el-alert v-if="lastResult.t1_comparison" :title="t1Title" :type="t1Type" :closable="false" show-icon style="margin-bottom:12px;">
        <template v-if="lastResult.t1_comparison.score != null">
          输出 vs 参考答案: <b>{{ lastResult.t1_comparison.score }}/100</b> — {{ lastResult.t1_comparison.note }}
        </template>
        <template v-else>
          {{ lastResult.t1_comparison.note }}
        </template>
      </el-alert>

      <!-- Baseline vs Actual -->
      <el-table v-if="lastResult.scores" :data="compareRows" size="small" border>
        <el-table-column prop="metric" label="指标" width="120" />
        <el-table-column prop="baseline" label="Baseline (基准)" width="150" />
        <el-table-column prop="actual" label="实际" width="150" />
        <el-table-column prop="delta" label="偏差" width="100">
          <template #default="{row}"><span :style="{color:row.bad?'#f56c6c':'#67c23a'}">{{ row.delta }}</span></template>
        </el-table-column>
      </el-table>

      <el-divider v-if="lastResult.scores" />
      <!-- TTTEC Scores -->
      <el-row v-if="lastResult.scores" :gutter="12">
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

      <el-button type="primary" size="small" style="margin-top:12px;" @click="goRun(lastResult.run_id)">
        查看版本详情 →
      </el-button>
    </el-card>

    <!-- History -->
    <el-card class="history-card" shadow="never">
      <template #header>
        <div class="card-title">
          <b>评测历史</b>
          <el-button size="small" @click="loadData" :loading="loading.manifests">刷新</el-button>
        </div>
      </template>
      <el-table :data="runs" empty-text="暂无评测记录" size="small" max-height="300">
        <el-table-column label="Run" width="100">
          <template #default="{row}">
            <el-link type="primary" @click="goRun(row.id)">{{ row.id?.substring(0,8) }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="run_label" label="版本" min-width="150" show-overflow-tooltip />
        <el-table-column prop="agent_name" label="Agent" width="120" show-overflow-tooltip />
        <el-table-column prop="model" label="模型" width="120" show-overflow-tooltip />
        <el-table-column label="来源" width="100">
          <template #default="{row}">
            <el-tag size="small" type="info">{{ row.source || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Trace" width="100">
          <template #default="{row}">
            <el-tag size="small" :type="row.trace_quality==='degraded'?'warning':'success'">{{ row.trace_quality || '-' }}</el-tag>
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
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheckFilled } from '@element-plus/icons-vue'

const router = useRouter()

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
  mode: 'offline',
  benchmarkRoot: '../evaluations/industrial-demo',
  runLabel: 'alarm-with-skill',
  benchmark_id: '',
  question_id: '',
  traceFile: null as File | null,
  traceName: '',
  useJudge: false,
})

const canRun = computed(() => {
  if (form.mode === 'offline') return form.benchmarkRoot && form.runLabel
  return form.benchmark_id && form.question_id && form.traceFile
})

const selectedQuestion = computed(() => questions.value.find((q:any) => q.question_id === form.question_id))
const completedRuns = computed(() => runs.value.filter((run:any) => run.status === 'COMPLETED').length)
const latestRunLabel = computed(() => {
  const latest = runs.value[0]
  return latest?.run_label || latest?.id?.substring(0, 8) || '-'
})
const previewQuestion = computed(() => {
  if (form.mode === 'single') return form.question_id || '{qid}'
  return 'alarm_analysis-0003'
})
const directoryChecks = computed(() => {
  if (form.mode === 'offline') {
    return [
      { label: 'Benchmark Root', value: form.benchmarkRoot || '未填写', ok: Boolean(form.benchmarkRoot) },
      { label: 'Run Label', value: form.runLabel || '未填写', ok: Boolean(form.runLabel) },
      { label: 'Trace Path', value: `runs/${form.runLabel || '{label}'}/${previewQuestion.value}/attempt-1/trace.jsonl`, ok: Boolean(form.runLabel) },
      { label: 'Output Dir', value: `runs/${form.runLabel || '{label}'}/${previewQuestion.value}/attempt-1/输出结果`, ok: Boolean(form.runLabel) },
    ]
  }
  return [
    { label: 'Manifest', value: form.benchmark_id || '未选择', ok: Boolean(form.benchmark_id) },
    { label: 'Question', value: form.question_id || '未选择', ok: Boolean(form.question_id) },
    { label: 'Trace File', value: form.traceName || '未选择', ok: Boolean(form.traceFile) },
    { label: 'Mode', value: '单 Trace 调试', ok: true },
  ]
})
const stepActive = computed(() => {
  if (running.value) return 2
  if (lastResult.value) return 4
  if (canRun.value) return 1
  return 0
})

const t1Type = computed(() => {
  const c = lastResult.value?.t1_comparison
  if (!c) return 'info'
  if (c.score == null) return 'warning'
  return c.score >= 80 ? 'success' : c.score >= 60 ? 'warning' : 'error'
})
const t1Title = computed(() => {
  const c = lastResult.value?.t1_comparison
  if (!c) return ''
  if (c.score == null) return '⚠️ T1 任务完成度: 无法验证输出'
  return `T1 任务完成度: ${c.score >= 80 ? '通过' : c.score >= 60 ? '部分通过' : '未通过'}`
})

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

function useDemoBundle() {
  form.benchmarkRoot = '../evaluations/industrial-demo'
  form.runLabel = 'alarm-with-skill'
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
    if (form.mode === 'offline') {
      const res = await axios.post(`${API}/runs/evaluate-offline`, {
        benchmark_root: form.benchmarkRoot,
        run_label: form.runLabel,
        judge_enabled: form.useJudge,
      })
      lastResult.value = res.data
      ElMessage.success(`离线评测完成，生成 ${res.data.score_count} 条评分`)
      await loadData()
      return
    }

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

function goRun(id: string) { router.push(`/runs/${id}`).catch(()=>{window.location.href=`/runs/${id}`}) }

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

<style scoped>
.dashboard-shell {
  max-width: 1280px;
  margin: 0 auto;
  text-align: left;
}

.dashboard-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(360px, 0.8fr);
  gap: 24px;
  align-items: stretch;
  margin-bottom: 20px;
}

.dashboard-hero h1 {
  margin: 4px 0 8px;
  font-size: 34px;
  line-height: 1.15;
  letter-spacing: 0;
  font-weight: 650;
}

.eyebrow {
  color: #5b6b83;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
}

.hero-copy {
  color: #667085;
  font-size: 15px;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.hero-metrics > div {
  background: #fff;
  border: 1px solid #e6e8ef;
  border-radius: 8px;
  padding: 18px;
  min-width: 0;
}

.hero-metrics span {
  display: block;
  color: #172033;
  font-size: 26px;
  font-weight: 700;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hero-metrics small {
  color: #7a8495;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(380px, 0.85fr);
  gap: 16px;
  margin-bottom: 16px;
}

.run-panel,
.result-card,
.history-card {
  border-radius: 8px;
}

.card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.form-stack {
  display: grid;
  gap: 12px;
}

.quick-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.muted-line {
  color: #7a8495;
  font-size: 13px;
}

.run-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 18px;
  gap: 12px;
}

.check-list {
  display: grid;
  gap: 12px;
}

.check-item {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
}

.check-item b,
.check-item span {
  display: block;
}

.offline-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.offline-summary > div {
  border: 1px solid #e8ebf2;
  border-radius: 8px;
  padding: 14px;
  background: #fbfcff;
  min-width: 0;
}

.offline-summary span,
.offline-summary b {
  display: block;
}

.offline-summary span {
  color: #788397;
  font-size: 12px;
}

.offline-summary b {
  color: #20283a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.check-item b {
  color: #2b3345;
  font-size: 13px;
}

.check-item span {
  color: #687386;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.ok {
  color: #17a36b;
}

.pending {
  color: #b8c0cc;
}

@media (max-width: 960px) {
  .dashboard-hero,
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .hero-metrics {
    grid-template-columns: 1fr;
  }

  .offline-summary {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
