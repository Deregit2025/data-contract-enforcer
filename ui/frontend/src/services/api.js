import axios from 'axios'

const api = axios.create({ baseURL: 'http://localhost:8000' })

export const getHealth        = () => api.get('/api/health').then(r => r.data)
export const getContracts     = () => api.get('/api/contracts').then(r => r.data)
export const getContractHealth= () => api.get('/api/contracts/health').then(r => r.data)
export const getContractResults = (id) => api.get(`/api/contracts/${id}/results`).then(r => r.data)
export const getViolations    = (params) => api.get('/api/violations', { params }).then(r => r.data)
export const getAllFailures    = () => api.get('/api/failures').then(r => r.data)
export const getViolationSummary = () => api.get('/api/violations/summary').then(r => r.data)
export const getSchemaChanges = () => api.get('/api/schema-changes').then(r => r.data)
export const getAiMetrics     = () => api.get('/api/ai-metrics').then(r => r.data)
export const getInterfaces    = () => api.get('/api/interfaces').then(r => r.data)
export const getSubscriptions = () => api.get('/api/interfaces/subscriptions').then(r => r.data)
