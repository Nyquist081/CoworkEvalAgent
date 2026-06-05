<template>
  <v-chart :option="option" style="height: 400px;" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const props = defineProps<{
  labels: string[]
  overallScores: number[]
  passAtKPcts: number[]
  passPowerKPcts: number[]
}>()

const option = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['总分', 'pass@k', 'pass^k'] },
  xAxis: { type: 'category', data: props.labels },
  yAxis: { type: 'value', min: 0, max: 100 },
  series: [
    {
      name: '总分', type: 'line', data: props.overallScores,
      smooth: true, lineStyle: { width: 3 },
    },
    {
      name: 'pass@k', type: 'line', data: props.passAtKPcts,
      smooth: true, lineStyle: { type: 'dashed' },
    },
    {
      name: 'pass^k', type: 'line', data: props.passPowerKPcts,
      smooth: true, lineStyle: { type: 'dotted' },
    },
  ],
}))
</script>
