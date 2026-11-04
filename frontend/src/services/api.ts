import axios, { AxiosError } from 'axios';
import { message } from 'antd';

/**
 * 统一错误结构：
 * - status：HTTP 状态码（网络错误为 0）
 * - code：后端错误码或 'NETWORK_ERROR' / 'TIMEOUT'
 * - requestId：本次请求的追踪 ID，便于对照后端日志
 * - handled：是否已由全局拦截器提示，业务层可用它避免重复提示
 */
export interface ApiError extends Error {
  status: number;
  code: string;
  requestId?: string;
  detail?: string;
  handled: boolean;
}

const rawBaseURL = (import.meta as any).env?.VITE_API_BASE_URL as string | undefined;

const api = axios.create({
  // 部署时可通过 VITE_API_BASE_URL 指向独立后端；默认走同源 /api（本地由 Vite 代理）
  baseURL: rawBaseURL ? rawBaseURL.replace(/\/$/, '') : '/api',
  timeout: 30_000,
});

const requestId = () => {
  const cryptoObj = typeof globalThis !== 'undefined' ? (globalThis as any).crypto : undefined;
  if (cryptoObj?.randomUUID) return cryptoObj.randomUUID();
  return `req-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
};

/** 后端返回的错误详情可能是字符串，也可能是校验错误数组 */
const normalizeDetail = (detail: unknown): string => {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (item && typeof item === 'object' ? (item as any).msg || JSON.stringify(item) : String(item)))
      .join('; ');
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail);
  return '';
};

const toApiError = (error: AxiosError): ApiError => {
  const status = error.response?.status ?? 0;
  const data: any = error.response?.data ?? {};
  const isTimeout = error.code === 'ECONNABORTED';
  const detail = normalizeDetail(data.detail) || normalizeDetail(data.message);

  let code = data.code || 'UNKNOWN';
  let text = detail;
  if (isTimeout) {
    code = 'TIMEOUT';
    text = '请求超时，请稍后重试';
  } else if (!error.response) {
    code = 'NETWORK_ERROR';
    text = '网络异常，请检查后端服务是否启动';
  } else if (status === 401) {
    code = 'UNAUTHORIZED';
    text = '登录状态已失效，请重新登录';
  } else if (status === 403) {
    code = 'FORBIDDEN';
    text = detail || '没有权限执行该操作';
  } else if (status >= 500) {
    code = 'SERVER_ERROR';
    text = detail || '服务端异常，请稍后重试';
  } else if (!text) {
    text = `请求失败（${status}）`;
  }

  const apiError = new Error(text) as ApiError;
  apiError.status = status;
  apiError.code = code;
  apiError.detail = detail;
  apiError.requestId = (error.config?.headers?.['X-Request-Id'] as string) || error.config?.headers?.['x-request-id'] as string;
  apiError.handled = false;
  return apiError;
};

/** 业务层取错误文案：优先用后端 detail，其次用统一兜底文案 */
export const getErrorMessage = (error: unknown, fallback = '操作失败'): string => {
  const err = error as ApiError;
  return err?.message || fallback;
};

/** 轻量埋点：关键操作留痕，便于排查用户路径（不引入第三方 SDK） */
const eventBuffer: Array<{ name: string; payload?: Record<string, unknown>; at: number }> = [];
export const trackEvent = (name: string, payload?: Record<string, unknown>) => {
  eventBuffer.push({ name, payload, at: Date.now() });
  if (eventBuffer.length > 200) eventBuffer.shift();
  if ((import.meta as any).env?.DEV) {
    // eslint-disable-next-line no-console
    console.debug('[track]', name, payload);
  }
};
export const getTrackedEvents = () => [...eventBuffer];

api.interceptors.request.use((config) => {
  const id = requestId();
  config.headers = config.headers || {};
  config.headers['X-Request-Id'] = id;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const apiError = toApiError(error);
    // 只对网络/超时/鉴权/服务端异常做全局提示；业务 4xx 交给调用方按场景提示，避免重复弹窗
    const needsGlobalToast =
      apiError.code === 'NETWORK_ERROR' ||
      apiError.code === 'TIMEOUT' ||
      apiError.status === 401 ||
      apiError.status >= 500;
    if (needsGlobalToast) {
      message.error(apiError.message);
      apiError.handled = true;
    }
    return Promise.reject(apiError);
  }
);

// ======================== LLM Config ========================

export const listLLMConfigs = () => api.get('/llm-configs').then(r => r.data);
export const createLLMConfig = (data: any) => api.post('/llm-configs', data).then(r => r.data);
export const updateLLMConfig = (id: number, data: any) => api.put(`/llm-configs/${id}`, data).then(r => r.data);
export const deleteLLMConfig = (id: number) => api.delete(`/llm-configs/${id}`);
export const testLLMConfig = (id: number) => api.post(`/llm-configs/${id}/test`).then(r => r.data);
export const testLLMConfigDraft = (data: any) => api.post('/llm-configs/test-draft', data).then(r => r.data);

// ======================== Dataset ========================

export const listDatasets = () => api.get('/datasets').then(r => r.data);
export const createDataset = (data: any) => api.post('/datasets', data).then(r => r.data);
export const getDataset = (id: number) => api.get(`/datasets/${id}`).then(r => r.data);
export const deleteDataset = (id: number) => api.delete(`/datasets/${id}`);
export const listDatasetRows = (id: number, page = 1, pageSize = 20) =>
  api.get(`/datasets/${id}/rows`, { params: { page, page_size: pageSize } }).then(r => r.data);
export const createDatasetRow = (id: number, data: any) =>
  api.post(`/datasets/${id}/rows`, data).then(r => r.data);
export const deleteDatasetRow = (id: number, rowId: number) =>
  api.delete(`/datasets/${id}/rows/${rowId}`);
export const importDataset = (id: number, file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post(`/datasets/${id}/import`, fd).then(r => r.data);
};
export const exportDataset = (id: number, format: 'csv' | 'json') =>
  api.get(`/datasets/${id}/export`, { params: { format }, responseType: 'blob' }).then(r => ({
    blob: r.data as Blob,
    contentDisposition: r.headers['content-disposition'] as string | undefined,
    contentType: r.headers['content-type'] as string | undefined,
  }));

// ======================== RAG Dataset Jobs ========================

export const listRagDatasetJobs = () => api.get('/rag-dataset-jobs').then(r => r.data);
export const createRagDatasetJob = (data: any) => api.post('/rag-dataset-jobs', data).then(r => r.data);
export const getRagDatasetJob = (id: number) => api.get(`/rag-dataset-jobs/${id}`).then(r => r.data);
export const uploadRagDatasetJobDocuments = (id: number, files: File[]) => {
  const fd = new FormData();
  files.forEach((file) => fd.append('files', file));
  return api.post(`/rag-dataset-jobs/${id}/documents`, fd).then(r => r.data);
};
export const listRagDatasetJobChunks = (id: number, documentId?: number) =>
  api.get(`/rag-dataset-jobs/${id}/chunks`, { params: documentId ? { document_id: documentId } : undefined }).then(r => r.data);
export const listRagDatasetJobSamples = (id: number, page = 1, pageSize = 20, status?: string) =>
  api.get(`/rag-dataset-jobs/${id}/samples`, { params: { page, page_size: pageSize, status } }).then(r => r.data);
export const startRagDatasetJob = (id: number) => api.post(`/rag-dataset-jobs/${id}/start`).then(r => r.data);
export const retryFailedRagDatasetJob = (id: number) => api.post(`/rag-dataset-jobs/${id}/retry-failed`).then(r => r.data);

// ======================== Metric ========================

export const listMetrics = async () => {
  const first = await api.get('/metrics', { params: { page: 1, page_size: 100 } }).then(r => r.data);
  if (Array.isArray(first)) return first;

  const firstItems = first?.items || [];
  const total = Number(first?.total || firstItems.length);
  const pageSize = Number(first?.page_size || firstItems.length || 100);
  if (!total || firstItems.length >= total || !pageSize) return firstItems;

  const pageCount = Math.ceil(total / pageSize);
  const restPages = await Promise.all(
    Array.from({ length: pageCount - 1 }, (_, index) =>
      api.get('/metrics', { params: { page: index + 2, page_size: pageSize } }).then(r => r.data)
    )
  );
  return [
    ...firstItems,
    ...restPages.flatMap((page) => (Array.isArray(page) ? page : page?.items || [])),
  ];
};
export const createMetric = (data: any) => api.post('/metrics', data).then(r => r.data);
export const updateMetric = (id: number, data: any) => api.put(`/metrics/${id}`, data).then(r => r.data);
export const deleteMetric = (id: number) => api.delete(`/metrics/${id}`);

// ======================== Endpoint Targets ========================

export const listEndpointTargets = () => api.get('/endpoint-targets').then(r => r.data);
export const createEndpointTarget = (data: any) => api.post('/endpoint-targets', data).then(r => r.data);
export const updateEndpointTarget = (id: number, data: any) => api.put(`/endpoint-targets/${id}`, data).then(r => r.data);
export const deleteEndpointTarget = (id: number) => api.delete(`/endpoint-targets/${id}`);
export const testEndpointTarget = (id: number, data: any) => api.post(`/endpoint-targets/${id}/test`, data).then(r => r.data);

// ======================== Scenario ========================

export const listScenarios = async () => {
  const data = await api.get('/scenarios').then(r => r.data);
  if (Array.isArray(data)) return data;
  // 兼容分页包装或异常响应，避免调用方对非数组执行 map
  return Array.isArray(data?.items) ? data.items : [];
};
export const createScenario = (data: any) => api.post('/scenarios', data).then(r => r.data);
export const updateScenario = (id: number, data: any) => api.put(`/scenarios/${id}`, data).then(r => r.data);
export const getScenario = (id: number) => api.get(`/scenarios/${id}`).then(r => r.data);
export const deleteScenario = (id: number) => api.delete(`/scenarios/${id}`);
export const getPresetScenarios = () => api.get('/scenarios/presets').then(r => r.data);

// ======================== Evaluation ========================

export const listEvaluations = () => api.get('/evaluations').then(r => r.data);
export const createEvaluation = (data: any) => api.post('/evaluations', data).then(r => r.data);
export const debugEvaluation = (data: any) => api.post('/evaluations/debug', data).then(r => r.data);
export const getEvaluation = (id: number) => api.get(`/evaluations/${id}`).then(r => r.data);
export const getEvaluationLogs = (id: number) => api.get(`/evaluations/${id}/logs`).then(r => r.data);
export const cancelEvaluation = (id: number) => api.post(`/evaluations/${id}/cancel`);
export const testEvaluationEndpoint = (data: any) => api.post('/evaluations/test-endpoint', data).then(r => r.data);

// ======================== Report ========================

export const listReports = (params?: any) =>
  api.get('/reports', { params }).then(r => r.data);
export const getReportSummary = (evalId: number) =>
  api.get(`/reports/${evalId}/summary`).then(r => r.data);
export const getReportRows = (evalId: number, page = 1, pageSize = 20, status?: string) =>
  api.get(`/reports/${evalId}/rows`, { params: { page, page_size: pageSize, status } }).then(r => r.data);
export const getReportRowDetail = (evalId: number, rowId: number) =>
  api.get(`/reports/${evalId}/rows/${rowId}`).then(r => r.data);
export const updateReportRowReview = (evalId: number, rowId: number, data: any) =>
  api.patch(`/reports/${evalId}/rows/${rowId}/review`, data).then(r => r.data);
export const compareReport = (evalId: number, baselineEvalId: number) =>
  api.get(`/reports/${evalId}/compare`, { params: { baseline_eval_id: baselineEvalId } }).then(r => r.data);

// ======================== Blind Test ========================

export const listBlindTests = () => api.get('/blind-tests').then(r => r.data);
export const createBlindTest = (data: any) => api.post('/blind-tests', data).then(r => r.data);
export const getBlindTest = (id: number) => api.get(`/blind-tests/${id}`).then(r => r.data);
export const getBlindTestSummary = (id: number) => api.get(`/blind-tests/${id}/summary`).then(r => r.data);
export const getBlindTestRows = (id: number, page = 1, pageSize = 20, status?: string) =>
  api.get(`/blind-tests/${id}/rows`, { params: { page, page_size: pageSize, status } }).then(r => r.data);
export const voteBlindTestRow = (id: number, rowId: number, data: any) =>
  api.post(`/blind-tests/${id}/rows/${rowId}/vote`, data).then(r => r.data);
export const cancelBlindTest = (id: number) => api.post(`/blind-tests/${id}/cancel`).then(r => r.data);
export const testBlindTestTarget = (data: any) => api.post('/blind-tests/test-target', data).then(r => r.data);

// ======================== RSI ========================

export const listRsiLoops = (params?: any) =>
  api.get('/rsi/loops', { params }).then(r => r.data);
export const createRsiLoop = (data: any) => api.post('/rsi/loops', data).then(r => r.data);
export const getRsiLoop = (id: number) => api.get(`/rsi/loops/${id}`).then(r => r.data);
export const startRsiLoop = (id: number) => api.post(`/rsi/loops/${id}/start`).then(r => r.data);
export const cancelRsiLoop = (id: number) => api.post(`/rsi/loops/${id}/cancel`).then(r => r.data);
export const getRsiLoopLogs = (id: number, offset = 0) =>
  api.get(`/rsi/loops/${id}/logs`, { params: { offset } }).then(r => r.data);
export const listRsiIterations = (id: number) =>
  api.get(`/rsi/loops/${id}/iterations`).then(r => r.data);
export const getRsiIteration = (id: number) =>
  api.get(`/rsi/iterations/${id}`).then(r => r.data);
export const approveRsiIteration = (id: number, data?: any) =>
  api.post(`/rsi/iterations/${id}/approve`, data || {}).then(r => r.data);
export const rejectRsiIteration = (id: number, data: any) =>
  api.post(`/rsi/iterations/${id}/reject`, data).then(r => r.data);
export const rollbackRsiLoop = (id: number, data: any) =>
  api.post(`/rsi/loops/${id}/rollback`, data).then(r => r.data);
export const listRsiVersions = (scope: string, scopeId: number) =>
  api.get(`/rsi/configs/${scope}/${scopeId}/versions`).then(r => r.data);
export const listRsiLoopVersions = (loopId: number) =>
  api.get(`/rsi/loops/${loopId}/versions`).then(r => r.data);
export const restoreRsiVersion = (versionId: number, actor?: string) =>
  api.post(`/rsi/configs/versions/${versionId}/restore`, undefined, { params: { actor } }).then(r => r.data);
export const previewRsiProposal = (id: number, data?: any) =>
  api.post(`/rsi/proposals/${id}/preview`, data || {}).then(r => r.data);
export const getRsiCompare = (loopId: number, iterationId?: number) =>
  api.get(`/rsi/loops/${loopId}/compare`, {
    params: iterationId ? { iteration_id: iterationId } : undefined,
  }).then(r => r.data);
export const createRsiHardCases = (loopId: number, data?: any) =>
  api.post(`/rsi/loops/${loopId}/hard-cases`, data || {}).then(r => r.data);

export default api;
