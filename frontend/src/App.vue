<template>
  <el-container style="min-height: 100vh">
    <el-header class="app-header">
      <h2 @click="goHome">CoworkEval</h2>
      <nav class="app-menu">
        <button :class="{ active: route.path === '/' }" @click="goHome">评测操作台</button>
        <button :class="{ active: route.path === '/compare' }" @click="goCompare">版本对比</button>
      </nav>
    </el-header>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
const route = useRoute()
const router = useRouter()
function goHome() { router.push({name:'dashboard'}).catch(()=>{window.location.href='/'}) }
function goCompare() { window.location.href = '/compare' }
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  padding: 0 28px;
  color: #fff;
  background: #121827;
}

.app-header h2 {
  margin: 0;
  color: #fff;
  font-weight: 650;
  letter-spacing: 0;
  cursor: pointer;
}

.app-menu {
  display: flex;
  gap: 8px;
  margin-left: 36px;
}

.app-menu button {
  height: 36px;
  padding: 0 14px;
  border: 0;
  border-radius: 6px;
  color: #d0d6e1;
  background: transparent;
  cursor: pointer;
}

.app-menu button.active,
.app-menu button:hover {
  color: #fff;
  background: rgba(255,255,255,0.1);
}

.app-main {
  background: #f4f6fa;
  padding: 24px 28px;
}

@media (max-width: 640px) {
  .app-header {
    padding: 0 16px;
  }

  .app-header h2 {
    font-size: 20px;
  }

  .app-menu {
    margin-left: 16px;
  }

  .app-menu button {
    padding: 0 10px;
  }

  .app-main {
    padding: 20px 14px;
  }
}
</style>
