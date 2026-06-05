<template>
  <div>
    <el-button @click="goBack" style="margin-bottom:12px;" icon="ArrowLeft">返回 Dashboard</el-button>
    <h1>📈 多版本对比</h1>
    <el-card>
      <el-form inline>
        <el-form-item label="Run IDs (逗号分隔)">
          <el-input v-model="ids" placeholder="uuid1, uuid2" style="width:400px" />
        </el-form-item>
        <el-form-item><el-button type="primary" @click="load">加载对比</el-button></el-form-item>
      </el-form>
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
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const API='/coworkeval/v1'
const router = useRouter()
const ids = ref('')
const passRates = ref<any[]>([])
const loaded = ref(false)

function goBack() { router.push('/') }

async function load() {
  loaded.value = true
  try {
    const r = await axios.get(`${API}/compare/pass-rate`, { params: { run_ids: ids.value } })
    passRates.value = r.data.runs || []
  } catch(e) { console.error(e) }
}
</script>
