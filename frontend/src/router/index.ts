import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('../views/Dashboard.vue'),
    },
    {
      path: '/runs/:runId',
      name: 'version-detail',
      component: () => import('../views/VersionDetail.vue'),
    },
    {
      path: '/compare',
      name: 'multi-version',
      component: () => import('../views/MultiVersion.vue'),
    },
    {
      path: '/meta/:runId',
      name: 'meta-analysis',
      component: () => import('../views/MetaAnalysis.vue'),
    },
  ],
})

export default router
