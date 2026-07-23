/**
 * Antigravity-K API Client
 * =========================
 * Fetch wrapper with PIN auth, error handling, and SSE streaming support.
 */
// @ts-nocheck


const API_BASE = '/v1';

export interface ApiOptions extends RequestInit {
  suppressLog?: boolean;
  skipPinModal?: boolean;
}

/**
 * Base API request wrapper.
 */
export async function apiRequest<T = any>(
  endpoint: string,
  options: ApiOptions = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const { suppressLog = false, skipPinModal = false, ...fetchOptions } = options;

  const pin = localStorage.getItem('ag_access_pin');
  const headers = new Headers(fetchOptions.headers || {});
  headers.set('Content-Type', 'application/json');
  if (pin) {
    headers.set('X-Access-Pin', pin);
  }

  try {
    const resp = await fetch(url, {
      ...fetchOptions,
      headers,
    });

    if (!resp.ok) {
      if (resp.status === 401 && !skipPinModal) {
        // PIN auth required — dispatch event for PIN modal
        window.dispatchEvent(new CustomEvent('agk:pin-required'));
      }
      throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
    }

    return await resp.json();
  } catch (err) {
    if (!suppressLog) {
      console.error(`[API] Error (${endpoint}):`, err);
    }
    throw err;
  }
}

/**
 * SSE streaming chat completion.
 * Returns abort controller + response reader.
 */
export async function streamChatCompletion(
  payload: Record<string, any>,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: Error) => void,
  signal?: AbortSignal
) {
  try {
    const response = await fetch('/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      let eolIndex;

      while ((eolIndex = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, eolIndex).trim();
        buffer = buffer.slice(eolIndex + 1);

        if (line.startsWith('data: ') && line !== 'data: [DONE]') {
          try {
            const data = JSON.parse(line.slice(6));
            const content = data.choices?.[0]?.delta?.content;
            if (content) {
              onChunk(content);
            }
          } catch {
            // skip parse errors
          }
        }
      }
    }

    onDone();
  } catch (err: any) {
    if (err.name === 'AbortError') {
      onDone();
      return;
    }
    onError(err);
  }
}

/**
 * Fetch models list from backend.
 */
export interface ModelInfo {
  id: string;
  role?: string;
  description?: string;
}

export async function fetchModels(): Promise<ModelInfo[]> {
  const data = await apiRequest<{ data: ModelInfo[] }>('/models');
  return data.data || [];
}

/**
 * Health check.
 */
export interface HealthStatus {
  status: string;
  backends?: Record<string, any>;
  rag_index_files?: string;
  cov_active?: boolean;
  daily_spend_usd?: number;
  daily_budget_usd?: number;
}

export async function checkHealth(): Promise<HealthStatus> {
  return apiRequest<HealthStatus>('/health', { suppressLog: true });
}

/**
 * System metrics.
 */
export interface SystemMetrics {
  ok: boolean;
  memory_mb?: number;
  cpu_percent?: number;
  total_tokens?: number;
}

export async function fetchSystemMetrics(): Promise<SystemMetrics> {
  const resp = await fetch('/api/system/status', {
    headers: { 'X-Access-Pin': localStorage.getItem('ag_access_pin') || '' },
  } as any);
  if (!resp.ok) throw new Error('System status unavailable');
  return resp.json();
}
