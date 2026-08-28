/**
 * Antigravity-K API Client
 * =========================
 * Fetch wrapper with PIN auth, error handling, and SSE streaming support.
 */

import { createAccessPinHeaders } from '../utils/accessPinCredential';
import {
  CacheStatsResponseSchema,
  ChatCompletionChunkSchema,
  DebugModeResponseSchema,
  HealthStatusSchema,
  LogLevelListResponseSchema,
  LogLevelSetResponseSchema,
  ModelListResponseSchema,
  ModelOperationsStatusSchema,
  SetAllLogLevelsResponseSchema,
  SettingsResponseSchema,
  SettingsSaveResponseSchema,
  SystemMetricsSchema,
} from './clientSchema';
import type {
  CacheStats,
  CacheStatsResponse,
  DebugModeResponse,
  DebugModeResult,
  HealthStatus,
  LogLevelInfo,
  LogLevelListResponse,
  LogLevelSetResponse,
  LogLevelSetResult,
  ModelInfo,
  ModelOperationalMetric,
  ModelOperationsStatus,
  ModelProviderCapability,
  ModelQualityCalibrationStatus,
  SetAllLogLevelsResponse,
  SettingsData,
  SettingsSaveResponse,
  SystemMetrics,
} from './clientSchema';

export type {
  CacheStats,
  DebugModeResult,
  HealthStatus,
  LogLevelInfo,
  LogLevelListResponse,
  LogLevelSetResult,
  ModelInfo,
  ModelOperationalMetric,
  ModelOperationsStatus,
  ModelProviderCapability,
  ModelQualityCalibrationStatus,
  SystemMetrics,
  SettingsData,
  SettingsSaveResponse,
};

const API_BASE = '/v1';

export interface ApiOptions extends RequestInit {
  suppressLog?: boolean;
  skipPinModal?: boolean;
}

export type ChatCompletionPayload = Readonly<Record<string, unknown>>;

export type ChatStreamHandlers = Readonly<{
  onChunk: (text: string) => void;
  onDone: () => void;
  onError: (error: Error) => void;
}>;

type ParsedSseData = Readonly<{
  frames: readonly string[];
  remainder: string;
}>;

async function requestJson(
  url: string,
  endpoint: string,
  options: ApiOptions = {}
): Promise<unknown> {
  const { suppressLog = false, skipPinModal = false, ...fetchOptions } = options;

  const headers = createAccessPinHeaders(fetchOptions.headers);
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
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

    const raw: unknown = await resp.json();
    return raw;
  } catch (err) {
    if (!suppressLog) {
      console.error(`[API] Error (${endpoint}):`, err);
    }
    throw err;
  }
}

/**
 * Base API request wrapper.
 */
export async function apiRequest(
  endpoint: string,
  options: ApiOptions = {}
): Promise<unknown> {
  return requestJson(`${API_BASE}${endpoint}`, endpoint, options);
}

export async function apiRequestPath(
  path: string,
  options: ApiOptions = {}
): Promise<unknown> {
  return requestJson(path, path, options);
}

function parseSseData(input: string, flush: boolean): ParsedSseData {
  const normalized = input.replaceAll('\r\n', '\n').replaceAll('\r', '\n');
  const segments = normalized.split('\n\n');
  const trailing = segments.pop() ?? '';
  if (flush && trailing.length > 0) {
    segments.push(trailing);
  }

  const frames: string[] = [];
  for (const segment of segments) {
    const data: string[] = [];
    for (const line of segment.split('\n')) {
      if (line.startsWith(':')) continue;
      const separator = line.indexOf(':');
      const field = separator < 0 ? line : line.slice(0, separator);
      const rawValue = separator < 0 ? '' : line.slice(separator + 1);
      const value = rawValue.startsWith(' ') ? rawValue.slice(1) : rawValue;
      if (field === 'data') data.push(value);
    }
    if (data.length > 0) frames.push(data.join('\n'));
  }

  return {
    frames,
    remainder: flush ? '' : trailing,
  };
}

function emitChatFrame(frame: string, onChunk: (text: string) => void): void {
  if (frame === '[DONE]') return;

  let raw: unknown;
  try {
    raw = JSON.parse(frame);
  } catch {
    return;
  }

  const parsed = ChatCompletionChunkSchema.safeParse(raw);
  if (!parsed.success) return;
  const content = parsed.data.choices[0]?.delta.content;
  if (content) onChunk(content);
}

function isAbortError(error: unknown): boolean {
  return typeof error === 'object'
    && error !== null
    && 'name' in error
    && error.name === 'AbortError';
}

/**
 * SSE streaming chat completion.
 * Returns abort controller + response reader.
 */
export async function streamChatCompletion(
  payload: ChatCompletionPayload,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  try {
    const headers = createAccessPinHeaders({ 'Content-Type': 'application/json' });

    const response = await fetch('/v1/chat/completions', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal,
    });

    if (!response.ok) {
      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent('agk:pin-required'));
      }
      throw new Error(`Server returned ${response.status}`);
    }

    if (response.body === null) {
      throw new Error('Chat completion stream returned no response body.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseData(buffer, false);
      buffer = parsed.remainder;
      for (const frame of parsed.frames) emitChatFrame(frame, handlers.onChunk);
    }

    buffer += decoder.decode();
    const final = parseSseData(buffer, true);
    for (const frame of final.frames) emitChatFrame(frame, handlers.onChunk);
    handlers.onDone();
  } catch (err: unknown) {
    if (isAbortError(err)) {
      handlers.onDone();
      return;
    }
    handlers.onError(err instanceof Error ? err : new Error(String(err)));
  }
}

/**
 * Fetch models list from backend.
 */
export async function fetchModels(): Promise<ModelInfo[]> {
  const raw = await apiRequest('/models');
  return ModelListResponseSchema.parse(raw).data;
}

export async function fetchModelOperations(refresh = false): Promise<ModelOperationsStatus> {
  const raw = await apiRequest(`/models/operations${refresh ? '?refresh=true' : ''}`, {
    suppressLog: true,
  });
  return ModelOperationsStatusSchema.parse(raw);
}

/**
 * Health check.
 */
export async function checkHealth(): Promise<HealthStatus> {
  const raw = await apiRequest('/health', { suppressLog: true });
  return HealthStatusSchema.parse(raw);
}

/**
 * System metrics.
 */
export async function fetchSystemMetrics(): Promise<SystemMetrics> {
  const raw = await requestJson('/api/system/status', '/api/system/status');
  return SystemMetricsSchema.parse(raw);
}

/**
 * Cache stats.
 */
export async function fetchCacheStats(): Promise<CacheStatsResponse> {
  const raw = await requestJson('/api/system/cache-stats', '/api/system/cache-stats');
  return CacheStatsResponseSchema.parse(raw);
}

/**
 * Fetch all antigravity_k.* logger levels.
 */
export async function fetchLogLevels(): Promise<LogLevelListResponse> {
  const raw = await requestJson('/api/system/log-level', '/api/system/log-level');
  return LogLevelListResponseSchema.parse(raw);
}

/**
 * Set a specific logger's level.
 */
export async function setLogLevel(name: string, level: string): Promise<LogLevelSetResponse> {
  const raw = await requestJson('/api/system/log-level', '/api/system/log-level', {
    method: 'POST',
    body: JSON.stringify({ name, level }),
  });
  return LogLevelSetResponseSchema.parse(raw);
}

/**
 * Set all antigravity_k.* loggers to the same level.
 */
export async function setAllLogLevels(level: string): Promise<SetAllLogLevelsResponse> {
  const raw = await requestJson('/api/system/log-level/all', '/api/system/log-level/all', {
    method: 'POST',
    body: JSON.stringify({ level }),
  });
  return SetAllLogLevelsResponseSchema.parse(raw);
}

/**
 * Enable or disable debug mode.
 */
export async function setDebugMode(action: 'enable' | 'disable'): Promise<DebugModeResponse> {
  const raw = await requestJson('/api/system/debug-mode', '/api/system/debug-mode', {
    method: 'POST',
    body: JSON.stringify({ action }),
  });
  return DebugModeResponseSchema.parse(raw);
}

export async function fetchSettings(): Promise<SettingsData> {
  const raw = await requestJson('/api/settings', '/api/settings');
  return SettingsResponseSchema.parse(raw).settings;
}

export async function saveSettings(settings: Record<string, string>): Promise<SettingsSaveResponse> {
  const raw = await requestJson('/api/settings/env', '/api/settings/env', {
    method: 'POST',
    body: JSON.stringify(settings),
  });
  return SettingsSaveResponseSchema.parse(raw);
}
