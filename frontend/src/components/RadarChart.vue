<template>
  <v-chart :option="option" style="height: 400px;" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart as ERadar } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([ERadar, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  dimensions: string[]
  series: { label: string; values: number[] }[]
}>()

const option = computed(() => ({
  tooltip: {},
  legend: { data: props.series.map(s => s.label) },
  radar: {
    indicator: props.dimensions.map(d => ({ name: d, max: 100 })),
    center: ['50%', '55%'],
    radius: '65%',
  },
  series: props.series.map(s => ({
    type: 'radar',
    name: s.label,
    data: [{ value: s.values, name: s.label }],
  })),
}))
</script>
