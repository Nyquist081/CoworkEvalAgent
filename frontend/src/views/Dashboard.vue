<template>
  <div class="page-shell">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">评测操作台</p>
        <h1>开始一次 Agent 评测</h1>
        <p class="hero-copy">
          选择一个已准备好的评测目录，点击开始，就能生成版本记录和评分结果。
        </p>
      </div>
      <div class="stat-grid">
        <div class="stat-tile">
          <b>{{ runs.length }}</b>
          <span>全部记录</span>
        </div>
        <div class="stat-tile">
          <b>{{ completedRuns }}</b>
          <span>已完成</span>
        </div>
        <div class="stat-tile">
          <b>{{ latestRunLabel }}</b>
          <span>最近版本</span>
        </div>
      </div>
    </section>

    <section class="starter-grid">
      <el-card class="panel-card" shadow="never">
        <template #header>
          <div class="section-head">
            <div>
              <b>新手评测向导</b>
              <small>不需要理解 Trace 或目录细节，按步骤填写即可。</small>
            </div>
            <el-radio-group v-model="form.mode" size="small">
              <el-radio-button label="demo">快速体验</el-radio-button>
              <el-radio-button label="skillab">Skill 对照实验</el-radio-button>
              <el-radio-button label="offline">评测自己的结果</el-radio-button>
              <el-radio-button label="single">单文件调试</el-radio-button>
            </el-radio-group>
          </div>
        </template>

        <el-steps :active="wizardStep" finish-status="success" class="wizard-steps">
          <el-step title="选择数据" description="Demo 或评测目录" />
          <el-step title="确认设置" description="版本名和 Judge" />
          <el-step title="查看结果" description="生成评分记录" />
        </el-steps>

        <div v-if="form.mode === 'demo'" class="mode-card">
          <div class="mode-copy">
            <b>先跑一个内置示例</b>
            <span>适合第一次打开平台时验证完整流程。系统会使用仓库里的工业告警分析样例。</span>
          </div>
          <el-button @click="useDemoBundle">填入示例</el-button>
        </div>

        <div v-if="form.mode === 'skillab'" class="mode-card compare-mode">
          <div class="mode-copy">
            <b>跑一组无 Skill / 有 Skill 对照</b>
            <span>平台会先生成 baseline，再生成启用 Skill 的版本，最后自动评测并跳转多版本对比。</span>
          </div>
          <div class="button-row tight">
            <el-button @click="useSkillABDemo">填入演示示例</el-button>
            <el-button type="primary" plain @click="useClaudeSecurityDemo">填入 Claude 安全 Demo</el-button>
          </div>
        </div>

        <div v-if="form.mode === 'demo' || form.mode === 'offline'" class="field-grid">
          <label>
            <span>评测集目录</span>
            <el-input v-model="form.benchmarkRoot" placeholder="../evaluations/industrial-demo" />
            <small>这个目录里应包含 manifest.json 和 runs 文件夹。</small>
          </label>
          <label>
            <span>版本名称</span>
            <el-input v-model="form.runLabel" placeholder="alarm-with-skill" />
            <small>例如 baseline、skill-v2、gpt-5-exp。</small>
          </label>
        </div>

        <div v-if="form.mode === 'skillab'" class="field-grid">
          <label>
            <span>评测集目录</span>
            <el-input v-model="form.benchmarkRoot" placeholder="../evaluations/industrial-demo" />
            <small>目录里应包含 manifest.json；实验结果会写入 runs 文件夹。</small>
          </label>
          <label>
            <span>执行预设</span>
            <el-select v-model="form.preset">
              <el-option label="演示预设：立即生成样例" value="mock-demo" />
              <el-option label="Claude Code：使用后端配置" value="claude-code" />
            </el-select>
            <small>真实 Claude 命令只从后端配置读取，浏览器不能传任意命令。</small>
          </label>
          <label>
            <span>无 Skill 版本名</span>
            <el-input v-model="form.baselineRunLabel" placeholder="baseline-no-skill" />
            <small>这是对照组，用来判断 Claude 自己能做到什么程度。</small>
          </label>
          <label>
            <span>有 Skill 版本名</span>
            <el-input v-model="form.skillRunLabel" placeholder="alarm-with-skill" />
            <small>这是实验组，用来衡量 Skill 是否真的带来提升。</small>
          </label>
          <label>
            <span>模型名称</span>
            <el-input v-model="form.model" placeholder="claude-code / deepseek / demo" />
          </label>
          <label>
            <span>Skill 版本</span>
            <el-input v-model="form.skillVersion" placeholder="alarm_analysis@v1" />
          </label>
        </div>

        <div v-if="form.mode === 'single'" class="field-grid">
          <label>
            <span>评测集</span>
            <el-select v-model="form.benchmark_id" placeholder="选择评测集" @change="onBenchmarkChange" :loading="loading.manifests" clearable>
              <el-option
                v-for="manifest in manifests"
                :key="manifest.benchmark_id"
                :label="`${manifest.benchmark_id} (${manifest.total_questions}题)`"
                :value="manifest.benchmark_id"
              />
            </el-select>
          </label>
          <label>
            <span>题目</span>
            <el-select v-model="form.question_id" placeholder="选择题目" :disabled="!form.benchmark_id">
              <el-option
                v-for="question in questions"
                :key="question.question_id"
                :label="`${question.question_id} - ${question.question_name}`"
                :value="question.question_id"
              />
            </el-select>
          </label>
          <input ref="mfRef" type="file" accept=".json" style="display:none" @change="handleManifestUpload" />
          <input ref="trRef" type="file" accept=".jsonl" style="display:none" @change="handleTraceSelect" />
          <div class="button-row">
            <el-button @click="($refs.trRef as any)?.click()">选择 Trace 文件</el-button>
            <el-button @click="($refs.mfRef as any)?.click()" :loading="loading.uploadManifest">上传评测集</el-button>
            <el-tag v-if="form.traceName" type="success">{{ form.traceName }}</el-tag>
          </div>
        </div>

        <div class="settings-row">
          <el-checkbox v-model="form.useJudge">
            启用 Judge 模型
          </el-checkbox>
          <span>模型由后端配置控制，当前可使用 DeepSeek。</span>
        </div>

        <div class="action-strip">
          <el-button type="primary" size="large" :loading="running" :disabled="!canRun" @click="runEval">
            {{ running ? '评测中...' : '开始评测' }}
          </el-button>
          <el-button size="large" @click="loadData" :loading="loading.manifests">刷新记录</el-button>
        </div>

        <el-alert v-if="error.eval" :title="friendlyEvalError" type="error" :closable="false" show-icon />
        <el-alert v-if="uploadMsg" :title="uploadMsg" type="success" :closable="false" show-icon />
        <el-alert v-if="error.manifests" :title="friendlyManifestError" type="warning" :closable="false" show-icon />
      </el-card>

      <el-card class="panel-card" shadow="never">
        <template #header>
          <div class="section-head compact">
            <b>准备情况</b>
            <el-tag :type="canRun ? 'success' : 'warning'" effect="plain">
              {{ canRun ? '可以开始' : '还需填写' }}
            </el-tag>
          </div>
        </template>
        <div class="check-list">
          <div v-for="item in readinessChecks" :key="item.label" class="check-item">
            <el-icon :class="item.ok ? 'ok' : 'pending'"><CircleCheckFilled /></el-icon>
            <div>
              <b>{{ item.label }}</b>
              <span>{{ item.value }}</span>
            </div>
          </div>
        </div>
        <el-divider />
        <div class="plain-help">
          <b>评测目录应该长这样</b>
          <code>{{ directoryPreview }}</code>
          <p>平台会读取这个 Trace，再对输出结果和参考答案评分。</p>
        </div>
      </el-card>
    </section>

    <el-card v-if="lastResult" class="panel-card result-card" shadow="never">
      <template #header>
        <div class="section-head compact">
          <b>本次评测已完成</b>
          <el-tag type="success">已生成 {{ lastResult.score_count ?? 1 }} 条评分</el-tag>
        </div>
      </template>
      <div class="result-summary">
        <div>
          <span>{{ isPairResult ? '对照组' : '版本名称' }}</span>
          <b>{{ isPairResult ? lastResult.baseline.run_label : (lastResult.run_label || lastResult.question_name || '-') }}</b>
        </div>
        <div>
          <span>{{ isPairResult ? '实验组' : '评测集' }}</span>
          <b>{{ isPairResult ? lastResult.skill.run_label : (lastResult.benchmark_id || form.benchmark_id) }}</b>
        </div>
        <div>
          <span>Judge</span>
          <b>{{ lastResult.judge_enabled || form.useJudge ? '已启用' : '未启用' }}</b>
        </div>
        <div>
          <span>{{ isPairResult ? '对比编号' : '结果编号' }}</span>
          <b>{{ isPairResult ? `${shortId(lastResult.baseline.run_id)} / ${shortId(lastResult.skill.run_id)}` : shortId(lastResult.run_id) }}</b>
        </div>
      </div>
      <div class="button-row">
        <template v-if="isPairResult">
          <el-button type="primary" @click="goComparePair">查看对照结果</el-button>
          <el-button @click="goRun(lastResult.baseline.run_id)">查看 baseline</el-button>
          <el-button @click="goRun(lastResult.skill.run_id)">查看 Skill 版本</el-button>
        </template>
        <template v-else>
          <el-button type="primary" @click="goRun(lastResult.run_id)">查看结果详情</el-button>
          <el-button @click="goCompareWith(lastResult.run_id)">拿这个版本去对比</el-button>
        </template>
      </div>
    </el-card>

    <el-card class="panel-card" shadow="never">
      <template #header>
        <div class="section-head compact">
          <div>
            <b>结果中心</b>
            <small>最近生成的评测记录都在这里。</small>
          </div>
          <el-button size="small" @click="loadData" :loading="loading.manifests">刷新</el-button>
        </div>
      </template>
      <el-table :data="runs" empty-text="还没有评测记录，先点击上方“开始评测”" size="small" max-height="360">
        <el-table-column label="版本" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="run-name">
              <b>{{ row.run_label || shortId(row.id) }}</b>
              <span>{{ shortId(row.id) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="评测集" min-width="150" prop="benchmark_id" show-overflow-tooltip />
        <el-table-column label="模型" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.model || '未记录' }}</template>
        </el-table-column>
        <el-table-column label="Trace" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="row.trace_quality === 'degraded' ? 'warning' : 'success'">
              {{ traceQualityLabel(row.trace_quality) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="goRun(row.id)">查看结果</el-button>
            <el-button size="small" @click="goCompareWith(row.id)">对比</el-button>
            <el-button size="small" type="danger" plain @click="deleteRun(row.id)">删除</el-button>
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

const API = '/coworkeval/v1'
const router = useRouter()

const manifests = ref<any[]>([])
const questions = ref<any[]>([])
const runs = ref<any[]>([])
const lastResult = ref<any>(null)
const running = ref(false)
const uploadMsg = ref('')

const loading = reactive({ manifests: false, uploadManifest: false })
const error = reactive({ manifests: '', eval: '' })

const form = reactive({
  mode: 'demo',
  benchmarkRoot: '../evaluations/industrial-demo',
  runLabel: 'alarm-with-skill',
  preset: 'mock-demo',
  baselineRunLabel: 'baseline-no-skill',
  skillRunLabel: 'alarm-with-skill',
  model: '',
  skillVersion: 'alarm_analysis@demo',
  benchmark_id: '',
  question_id: '',
  traceFile: null as File | null,
  traceName: '',
  useJudge: false,
})

const completedRuns = computed(() => runs.value.filter((run: any) => run.status === 'COMPLETED').length)
const latestRunLabel = computed(() => runs.value[0]?.run_label || shortId(runs.value[0]?.id) || '-')
const selectedQuestion = computed(() => questions.value.find((question: any) => question.question_id === form.question_id))
const isPairResult = computed(() => Boolean(lastResult.value?.baseline && lastResult.value?.skill))
const canRun = computed(() => {
  if (form.mode === 'single') return form.benchmark_id && form.question_id && form.traceFile
  if (form.mode === 'skillab') {
    return form.benchmarkRoot && form.preset && form.baselineRunLabel && form.skillRunLabel
      && form.baselineRunLabel !== form.skillRunLabel
  }
  return form.benchmarkRoot && form.runLabel
})
const wizardStep = computed(() => {
  if (lastResult.value) return 3
  if (canRun.value) return 2
  if (form.mode) return 1
  return 0
})
const friendlyManifestError = computed(() => `${error.manifests}。请确认后端服务已启动。`)
const friendlyEvalError = computed(() => {
  const raw = error.eval || ''
  if (raw.includes('500')) return '评测失败。请确认评测目录、版本名称和 trace.jsonl 都存在。'
  if (raw.includes('Network')) return '无法连接后端服务。请先启动后端再重试。'
  return raw
})
const directoryPreview = computed(() => {
  if (form.mode === 'single') return '上传的 .jsonl Trace 文件'
  if (form.mode === 'skillab') {
    return `runs/${form.baselineRunLabel || 'baseline-no-skill'}/... + runs/${form.skillRunLabel || 'with-skill'}/...`
  }
  return `runs/${form.runLabel || '版本名称'}/题目ID/attempt-1/trace.jsonl`
})
const readinessChecks = computed(() => {
  if (form.mode === 'single') {
    return [
      { label: '评测集', value: form.benchmark_id || '请选择评测集', ok: Boolean(form.benchmark_id) },
      { label: '题目', value: selectedQuestion.value?.question_name || '请选择题目', ok: Boolean(form.question_id) },
      { label: 'Trace 文件', value: form.traceName || '请选择 .jsonl 文件', ok: Boolean(form.traceFile) },
      { label: '评分方式', value: form.useJudge ? '规则评分 + Judge' : '规则评分', ok: true },
    ]
  }
  if (form.mode === 'skillab') {
    return [
      { label: '评测集目录', value: form.benchmarkRoot || '请输入目录', ok: Boolean(form.benchmarkRoot) },
      { label: '执行预设', value: form.preset === 'mock-demo' ? '演示预设' : 'Claude Code 后端预设', ok: Boolean(form.preset) },
      { label: '对照组', value: form.baselineRunLabel || '请输入无 Skill 版本名', ok: Boolean(form.baselineRunLabel) },
      { label: '实验组', value: form.skillRunLabel || '请输入有 Skill 版本名', ok: Boolean(form.skillRunLabel) },
      { label: '版本名检查', value: form.baselineRunLabel === form.skillRunLabel ? '两个版本名不能相同' : '两个版本会分开保存', ok: form.baselineRunLabel !== form.skillRunLabel },
      { label: '评分方式', value: form.useJudge ? '规则评分 + Judge' : '规则评分', ok: true },
    ]
  }
  return [
    { label: '评测集目录', value: form.benchmarkRoot || '请输入目录', ok: Boolean(form.benchmarkRoot) },
    { label: '版本名称', value: form.runLabel || '请输入版本名称', ok: Boolean(form.runLabel) },
    { label: 'Trace 位置', value: directoryPreview.value, ok: Boolean(form.runLabel) },
    { label: '评分方式', value: form.useJudge ? '规则评分 + Judge' : '规则评分', ok: true },
  ]
})

function shortId(id?: string) {
  return id ? id.slice(0, 8) : '-'
}

function statusType(status: string) {
  if (status === 'COMPLETED') return 'success'
  if (status === 'FAILED') return 'danger'
  return 'warning'
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    COMPLETED: '已完成',
    FAILED: '失败',
    PENDING: '等待中',
    PARSING_TRACE: '读取 Trace',
    EVALUATING_BASELINE: '评分中',
    EVALUATING_JUDGE: 'Judge 中',
  }
  return labels[status] || status || '-'
}

function traceQualityLabel(quality: string) {
  if (quality === 'degraded') return '简化'
  if (quality === 'full') return '完整'
  return '未知'
}

function formatTime(value?: string) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function onBenchmarkChange(bid: string) {
  const manifest = manifests.value.find((item: any) => item.benchmark_id === bid)
  questions.value = manifest?.questions || []
  form.question_id = ''
}

function useDemoBundle() {
  form.mode = 'demo'
  form.benchmarkRoot = '../evaluations/industrial-demo'
  form.runLabel = 'alarm-with-skill'
}

function useSkillABDemo() {
  form.mode = 'skillab'
  form.benchmarkRoot = '../evaluations/industrial-demo'
  form.preset = 'mock-demo'
  form.baselineRunLabel = 'baseline-no-skill'
  form.skillRunLabel = 'alarm-with-skill'
  form.model = 'demo'
  form.skillVersion = 'alarm_analysis@demo'
}

function useClaudeSecurityDemo() {
  form.mode = 'skillab'
  form.benchmarkRoot = '../evaluations/skill-demo-pack'
  form.preset = 'claude-code'
  form.baselineRunLabel = 'security-baseline-no-skill'
  form.skillRunLabel = 'security-with-skill'
  form.model = 'haiku'
  form.skillVersion = 'security_review@v1'
  form.useJudge = false
}

function handleTraceSelect(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  form.traceFile = file || null
  form.traceName = file?.name || ''
}

async function loadData() {
  loading.manifests = true
  error.manifests = ''
  try {
    const [manifestRes, runRes] = await Promise.all([
      axios.get(`${API}/manifests`),
      axios.get(`${API}/runs`),
    ])
    manifests.value = manifestRes.data || []
    runs.value = (runRes.data || []).sort((a: any, b: any) => {
      return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
    })
    if (manifests.value.length && !form.benchmark_id) {
      form.benchmark_id = manifests.value[0].benchmark_id
      onBenchmarkChange(form.benchmark_id)
    }
  } catch (e: any) {
    error.manifests = `加载失败: ${e.response?.data?.detail || e.message}`
  } finally {
    loading.manifests = false
  }
}

async function handleManifestUpload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  loading.uploadManifest = true
  uploadMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await axios.post(`${API}/manifests/upload`, fd)
    uploadMsg.value = `已注册评测集：${res.data.benchmark_id}`
    ElMessage.success(uploadMsg.value)
    await loadData()
    form.benchmark_id = res.data.benchmark_id
    onBenchmarkChange(res.data.benchmark_id)
  } catch (e: any) {
    ElMessage.error(`上传失败：${e.response?.data?.detail || e.message}`)
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
    if (form.mode === 'skillab') {
      const res = await axios.post(`${API}/experiments/skill-ab`, {
        benchmark_root: form.benchmarkRoot,
        preset: form.preset,
        baseline_run_label: form.baselineRunLabel,
        skill_run_label: form.skillRunLabel,
        judge_enabled: form.useJudge,
        model: form.model,
        skill_version: form.skillVersion,
      })
      lastResult.value = res.data
      ElMessage.success('对照实验完成，已生成两个可比较版本')
      await loadData()
      return
    }

    if (form.mode !== 'single') {
      const res = await axios.post(`${API}/runs/evaluate-offline`, {
        benchmark_root: form.benchmarkRoot,
        run_label: form.runLabel,
        judge_enabled: form.useJudge,
      })
      lastResult.value = res.data
      ElMessage.success(`评测完成，生成 ${res.data.score_count} 条评分`)
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
    ElMessage.success('单文件评测完成')
    await loadData()
  } catch (e: any) {
    error.eval = `评测失败: ${e.response?.data?.detail || e.message}`
    ElMessage.error(friendlyEvalError.value)
  } finally {
    running.value = false
  }
}

function goRun(id: string) {
  router.push(`/runs/${id}`).catch(() => { window.location.href = `/runs/${id}` })
}

function goCompareWith(id: string) {
  window.location.href = `/compare?runs=${encodeURIComponent(id)}`
}

function goComparePair() {
  if (!lastResult.value?.compare_run_ids?.length) return
  const ids = lastResult.value.compare_run_ids.join(',')
  window.location.href = `/compare?runs=${encodeURIComponent(ids)}`
}

async function deleteRun(runId: string) {
  try {
    await ElMessageBox.confirm('删除后这个结果不会再出现在历史列表中。确定删除吗？', '删除评测结果', { type: 'warning' })
    await axios.delete(`${API}/runs/${runId}`)
    ElMessage.success('已删除')
    await loadData()
  } catch {}
}

onMounted(loadData)
</script>

<style scoped>
.page-shell {
  max-width: 1280px;
  margin: 0 auto;
  text-align: left;
}

.hero-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.8fr);
  gap: 24px;
  margin-bottom: 18px;
}

.hero-panel h1 {
  margin: 4px 0 8px;
  color: #111827;
  font-size: 34px;
  line-height: 1.15;
  letter-spacing: 0;
  font-weight: 700;
}

.eyebrow {
  color: #4f6f9f;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
}

.hero-copy,
.section-head small,
.plain-help p,
label small,
.settings-row span {
  color: #667085;
  font-size: 13px;
}

.stat-grid,
.result-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.result-summary {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.stat-tile,
.result-summary > div {
  min-width: 0;
  padding: 16px;
  border: 1px solid #e7eaf0;
  border-radius: 8px;
  background: #fff;
}

.stat-tile b,
.result-summary b {
  display: block;
  overflow: hidden;
  color: #172033;
  font-size: 24px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-summary b {
  font-size: 18px;
}

.stat-tile span,
.result-summary span {
  color: #7a8495;
  font-size: 12px;
}

.starter-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(360px, 0.75fr);
  gap: 16px;
  margin-bottom: 16px;
}

.panel-card {
  margin-bottom: 16px;
  border-radius: 8px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-head > div,
.run-name {
  display: grid;
  gap: 2px;
}

.compact {
  align-items: center;
}

.wizard-steps {
  margin-bottom: 20px;
}

.mode-card {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border: 1px solid #d8e6ff;
  border-radius: 8px;
  background: #f6f9ff;
}

.mode-copy {
  display: grid;
  gap: 4px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

label {
  display: grid;
  gap: 6px;
}

label > span {
  color: #2f394b;
  font-size: 13px;
  font-weight: 700;
}

.button-row,
.settings-row,
.action-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.settings-row {
  justify-content: space-between;
  padding-top: 14px;
}

.check-list {
  display: grid;
  gap: 12px;
}

.check-item {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 10px;
}

.check-item b,
.check-item span {
  display: block;
}

.check-item b {
  color: #2b3345;
  font-size: 13px;
}

.check-item span,
.plain-help code,
.run-name span {
  color: #687386;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.plain-help {
  display: grid;
  gap: 8px;
}

.plain-help code {
  display: block;
  padding: 10px;
  border-radius: 6px;
  background: #f3f5f8;
}

.ok {
  color: #17a36b;
}

.pending {
  color: #b8c0cc;
}

.run-name b {
  color: #1f2937;
}

@media (max-width: 960px) {
  .hero-panel,
  .starter-grid,
  .field-grid,
  .stat-grid,
  .result-summary {
    grid-template-columns: 1fr;
  }
}
</style>
