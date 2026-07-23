/**
 * Antigravity-K API Client
 * =========================
 * Fetch wrapper with PIN auth, error handling, and SSE streaming support.
 */

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

/**
 * Cache stats.
 */
export interface CacheStats {
  total_entries: number;
  total_tags: number;
  hits: number;
  misses: number;
  hit_ratio: number;
  memory_estimate_kb: number;
  entries: {
    key: string;
    ttl: number;
    age: number;
    remaining_ttl: number;
    tags: string[];
    hits: number;
  }[];
}

export async function fetchCacheStats(): Promise<{ ok: boolean; stats: CacheStats } | { ok: false; error: string }> {
  const pin = localStorage.getItem('ag_access_pin') || '';
  const resp = await fetch('/api/system/cache-stats', {
    headers: { 'X-Access-Pin': pin },
  } as any);
  return resp.json();
}

/**
 * Log level management types.
 */
export interface LogLevelInfo {
  name: string;
  level: number;
  level_name: string;
  effective_level: number;
  effective_level_name: string;
  handlers: number;
}

export interface LogLevelListResponse {
  ok: boolean;
  loggers: LogLevelInfo[];
  debug_mode: boolean;
  count: number;
}

export interface LogLevelSetResult {
  name: string;
  previous_level: number;
  current_level: number;
  previous_level_name: string;
  current_level_name: string;
}

export interface DebugModeResult {
  success: boolean;
  message: string;
  updated_count?: number;
  restored_count?: number;
}

/**
 * Fetch all antigravity_k.* logger levels.
 */
export async function fetchLogLevels(): Promise<LogLevelListResponse> {
  const pin = localStorage.getItem('ag_access_pin') || '';
  const resp = await fetch('/api/system/log-level', {
    headers: { 'X-Access-Pin': pin },
  } as any);
  return resp.json();
}

/**
 * Set a specific logger's level.
 */
export async function setLogLevel(name: string, level: string): Promise<{ ok: boolean; result?: LogLevelSetResult; error?: string }> {
  const pin = localStorage.getItem('ag_access_pin') || '';
  const resp = await fetch('/api/system/log-level', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Access-Pin': pin },
    body: JSON.stringify({ name, level }),
  } as any);
  return resp.json();
}

/**
 * Set all antigravity_k.* loggers to the same level.
 */
export async function setAllLogLevels(level: string): Promise<{ ok: boolean; result?: any; error?: string }> {
  const pin = localStorage.getItem('ag_access_pin') || '';
  const resp = await fetch('/api/system/log-level/all', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Access-Pin': pin },
    body: JSON.stringify({ level }),
  } as any);
  return resp.json();
}

/**
 * Enable or disable debug mode.
 */
export async function setDebugMode(action: 'enable' | 'disable'): Promise<{ ok: boolean; debug_mode: boolean; result?: DebugModeResult; error?: string }> {
  const pin = localStorage.getItem('ag_access_pin') || '';
  const resp = await fetch('/api/system/debug-mode', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Access-Pin': pin },
    body: JSON.stringify({ action }),
  } as any);
  return resp.json();
}
