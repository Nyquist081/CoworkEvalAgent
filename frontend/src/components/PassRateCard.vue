<template>
  <el-card shadow="hover">
    <template #header>{{ title }}</template>
    <el-row :gutter="8">
      <el-col :span="8">
        <div style="text-align: center;">
          <div style="font-size: 32px; font-weight: bold; color: #409eff;">{{ passAtK }}%</div>
          <div style="font-size: 12px; color: #999;">pass@k</div>
        </div>
      </el-col>
      <el-col :span="8">
        <div style="text-align: center;">
          <div style="font-size: 32px; font-weight: bold; color: #67c23a;">{{ passPowerK }}%</div>
          <div style="font-size: 12px; color: #999;">pass^k</div>
        </div>
      </el-col>
      <el-col :span="8">
        <div style="text-align: center;">
          <div style="font-size: 32px; font-weight: bold;" :style="{ color: gapColor }">{{ ppGap }}%</div>
          <div style="font-size: 12px; color: #999;">PP 差值</div>
        </div>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  title: string
  passAtK: number
  passPowerK: number
  ppGap: number
}>()

const gapColor = computed(() => props.ppGap > 20 ? '#f56c6c' : props.ppGap > 10 ? '#e6a23c' : '#67c23a')
</script>
