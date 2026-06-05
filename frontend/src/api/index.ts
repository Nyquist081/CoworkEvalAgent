import apiClient from './client'

export const runsApi = {
  list: (params?: { benchmark_id?: string; status?: string }) =>
    apiClient.get('/runs', { params }),
  get: (runId: string) => apiClient.get(`/runs/${runId}`),
  create: (data: any) => apiClient.post('/runs', data),
  delete: (runId: string) => apiClient.delete(`/runs/${runId}`),
  triggerJudge: (runId: string) => apiClient.post(`/runs/${runId}/trigger-judge`),
}

export const scoresApi = {
  list: (runId: string) => apiClient.get(`/runs/${runId}/scores`),
  get: (runId: string, questionId: string) =>
    apiClient.get(`/runs/${runId}/scores/${questionId}`),
  summary: (runId: string) => apiClient.get(`/runs/${runId}/scores/summary`),
}

export const manifestsApi = {
  list: () => apiClient.get('/manifests'),
  get: (benchmarkId: string) => apiClient.get(`/manifests/${benchmarkId}`),
  create: (data: any) => apiClient.post('/manifests', data),
}

export const compareApi = {
  radar: (runIds: string) => apiClient.get('/compare/radar', { params: { run_ids: runIds } }),
  heatmap: (runIds: string) => apiClient.get('/compare/heatmap', { params: { run_ids: runIds } }),
  trend: (benchmarkId: string) => apiClient.get('/compare/trend', { params: { benchmark_id: benchmarkId } }),
  passRate: (runIds: string) => apiClient.get('/compare/pass-rate', { params: { run_ids: runIds } }),
}

export const metaApi = {
  passRate: (runId: string) => apiClient.get(`/meta/${runId}/pass-rate`),
  commonIssues: (runId: string) => apiClient.get(`/meta/${runId}/common-issues`),
  extract: (runId: string) => apiClient.post(`/meta/${runId}/extract`),
}
