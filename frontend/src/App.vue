<template>
  <el-container style="min-height: 100vh">
    <el-header style="background: #1a1a2e; color: white; display: flex; align-items: center; padding: 0 24px;">
      <h2 style="margin: 0; font-weight: 300;">CoworkEval</h2>
      <el-menu mode="horizontal" :default-active="route.path" router
        style="margin-left: 40px; border-bottom: none; background: transparent;">
        <el-menu-item index="/" style="color: #ccc;">📊 Dashboard</el-menu-item>
        <el-menu-item index="/compare" style="color: #ccc;">📈 多版本对比</el-menu-item>
      </el-menu>
    </el-header>
    <el-main style="background: #f5f7fa;">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>
