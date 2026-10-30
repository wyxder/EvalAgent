/**
 * 评测进度 SSE 订阅。
 * 优先使用服务端推送；连续失败时回调 onFallback，由调用方降级为轮询。
 */
export interface EvaluationStreamPayload {
  task_id: number;
  status: string;
  progress: number;
  total_rows: number;
  completed_rows: number;
  logs: string;
  error?: string;
}

export interface EvaluationStreamHandlers {
  onMessage: (payload: EvaluationStreamPayload) => void;
  onFallback?: () => void;
  onClose?: () => void;
}

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled']);

export const subscribeEvaluationStream = (
  taskId: number,
  handlers: EvaluationStreamHandlers
): (() => void) => {
  let errors = 0;
  let disposed = false;
  const source = new EventSource(`/api/evaluations/${taskId}/stream`);

  const close = () => {
    if (disposed) return;
    disposed = true;
    source.close();
    handlers.onClose?.();
  };

  source.onmessage = (event) => {
    errors = 0;
    try {
      const payload = JSON.parse(event.data) as EvaluationStreamPayload;
      if (payload.error) {
        handlers.onFallback?.();
        close();
        return;
      }
      handlers.onMessage(payload);
      if (TERMINAL_STATUSES.has(payload.status)) close();
    } catch {
      // 忽略无法解析的心跳/脏数据
    }
  };

  source.onerror = () => {
    errors += 1;
    // EventSource 自带重连；连续 3 次仍失败则交给调用方降级为轮询
    if (errors >= 3) {
      handlers.onFallback?.();
      close();
    }
  };

  return () => {
    close();
  };
};
