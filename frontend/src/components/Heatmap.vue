<template>
  <v-chart :option="option" style="height: 400px;" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { HeatmapChart } from 'echarts/charts'
import { TooltipComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([HeatmapChart, TooltipComponent, VisualMapComponent, CanvasRenderer])

const props = defineProps<{
  questions: string[]
  dimensions: string[]
  data: number[][]
}>()

const option = computed(() => ({
  tooltip: { formatter: (p: any) => `${p.value[0]} - ${p.value[1]}: ${p.value[2]}` },
  xAxis: { type: 'category', data: props.dimensions, axisLabel: { rotate: 0 } },
  yAxis: { type: 'category', data: props.questions },
  visualMap: { min: 0, max: 100, calculable: true, orient: 'horizontal', left: 'center' },
  series: [{
    type: 'heatmap',
    data: props.data.flatMap((row, i) =>
      row.map((val, j) => [j, i, val])
    ),
    label: { show: true, fontSize: 10 },
  }],
}))
</script>
