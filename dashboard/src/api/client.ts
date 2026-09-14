/**
 * Ssak-Ai API Client
 * =========================
 * Fetch wrapper with PIN auth, error handling, and SSE streaming support.
 */

import { createAccessPinHeaders } from '../utils/accessPinCredential';
import {
  createProjectIdentityHeaders,
  withProjectIdentityPayload,
} from './projectIdentity';
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
  SettingsDeleteResponseSchema,
  SettingsSaveResponseSchema,
  SessionDisclosureSchema,
  SystemMetricsSchema,
  LocalModelsResponseSchema,
  TrainingRecipeSchema,
  McpHealthResponseSchema,
  McpOAuthStatusResponseSchema,
  McpOAuthStartResponseSchema,
  AgentAskResponseSchema,
} from './clientSchema';
import type {
  AgentAskRequest,
  AgentAskResponse,
  LocalModelItem,
  LocalModelsResponse,
  CacheStats,
  CacheStatsResponse,
  McpHealthEntry,
  McpHealthResponse,
  McpOAuthServerStatus,
  McpOAuthStatusResponse,
  McpOAuthStartResponse,
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
  SettingsDeleteResponse,
  SettingsSaveResponse,
  SessionDisclosure,
  DisclosureLevel,
  LimitDisclosure,
  SystemMetrics,
  TrainingRecipe,
  TrainingRecipesResponse,
} from './clientSchema';

export type {
  AgentAskRequest,
  AgentAskResponse,
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
  SessionDisclosure,
  DisclosureLevel,
  LimitDisclosure,
  SystemMetrics,
  TrainingRecipe,
  TrainingRecipesResponse,
  LocalModelItem,
  LocalModelsResponse,
  McpHealthResponse,
  McpHealthEntry,
  McpOAuthServerStatus,
  McpOAuthStatusResponse,
  McpOAuthStartResponse,
  SettingsData,
  SettingsDeleteResponse,
  SettingsSaveResponse,
};

const API_BASE = '/v1';

export interface ApiOptions extends RequestInit {
  suppressLog?: boolean;
  skipPinModal?: boolean;
}

/**
 * JSON API 호출이 2xx가 아닌 응답을 받았을 때 던지는 오류 (CR-06).
 *
 * 메시지 형식은 예전과 같은 `HTTP <status>: <statusText>`로 유지하되,
 * 호출자가 문자열을 파싱하지 않고 상태 코드로 분기할 수 있게 `status`를 싣는다
 * (예: 설정 화면이 401을 기존 PIN 흐름 안내로 연결한다).
 */
export class ApiHttpError extends Error {
  readonly status: number;

  constructor(status: number, statusText: string) {
    super(`HTTP ${status}: ${statusText}`);
    this.name = 'ApiHttpError';
    this.status = status;
  }
}

/** 401(PIN 인증 필요) 응답인가 — 페이지가 인증 안내를 띄울 때 쓴다. */
export function isAuthRequiredError(error: unknown): boolean {
  return error instanceof ApiHttpError && error.status === 401;
}

export type ChatCompletionPayload = Readonly<Record<string, unknown>>;


/** CTX-01 revision conflict (HTTP 409). Full wire helpers live below. */
export class ConversationRevisionConflictError extends Error {
  readonly status = 409;
  readonly payload: {
    ok: false;
    error: 'stale_conversation_revision';
    detail: string;
    conversation_id: string;
    expected_revision: number;
    current_revision: number;
    correlation_id?: string;
  };

  constructor(payload: ConversationRevisionConflictError['payload']) {
    super(payload.detail || 'Conversation revision conflict');
    this.name = 'ConversationRevisionConflictError';
    this.payload = payload;
  }
}

/**
 * CR-01: typed failure for conversation API errors that are not revision conflicts.
 *
 * `code` carries the frozen wire error code (`conversation_not_found`,
 * `conversation_integrity_error`, `conversation_storage_migration_required`, ...)
 * so the UI can distinguish "this conversation does not exist yet" from
 * "the server cannot serve this conversation's stored bytes".
 */
export class ConversationRequestError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = 'ConversationRequestError';
    this.code = code;
    this.status = status;
  }
}

export type ChatStreamHandlers = Readonly<{
  onChunk: (text: string) => void;
  onDone: () => void;
  onError: (error: Error) => void;
  /** CTX-01: authoritative conversation snapshot from SSE trailer */
  onConversationSnapshot?: (snapshot: {
    conversation_id: string;
    project_id: string;
    revision: number;
    message_count: number;
    summary?: string | null;
    retained_message_ids?: string[];
  }) => void;
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

  const headers = createProjectIdentityHeaders(fetchOptions.headers);
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
      throw new ApiHttpError(resp.status, resp.statusText);
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

function emitChatFrame(
  frame: string,
  onChunk: (text: string) => void,
  onConversationSnapshot?: ChatStreamHandlers['onConversationSnapshot'],
): void {
  if (frame === '[DONE]') return;

  let raw: unknown;
  try {
    raw = JSON.parse(frame);
  } catch {
    return;
  }

  // CTX-01 F2: mid-stream compact race — typed conflict SSE (reuse 409 UX).
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    const conflictPayload = (
      obj.agk_conversation_conflict
      && typeof obj.agk_conversation_conflict === 'object'
    )
      ? obj.agk_conversation_conflict as Record<string, unknown>
      : (obj.error === 'stale_conversation_revision' ? obj : null);
    if (conflictPayload) {
      throw new ConversationRevisionConflictError({
        ok: false,
        error: 'stale_conversation_revision',
        detail: String(conflictPayload.detail || 'Conversation revision conflict'),
        conversation_id: String(conflictPayload.conversation_id || ''),
        expected_revision: Number(conflictPayload.expected_revision ?? 0),
        current_revision: Number(conflictPayload.current_revision ?? 0),
        correlation_id: conflictPayload.correlation_id
          ? String(conflictPayload.correlation_id)
          : undefined,
      });
    }
  }

  if (
    raw
    && typeof raw === 'object'
    && 'agk_conversation' in raw
    && (raw as { agk_conversation?: unknown }).agk_conversation
    && typeof (raw as { agk_conversation: unknown }).agk_conversation === 'object'
  ) {
    const snap = (raw as { agk_conversation: {
      conversation_id: string;
      project_id: string;
      revision: number;
      message_count: number;
      summary?: string | null;
      retained_message_ids?: string[];
    } }).agk_conversation;
    onConversationSnapshot?.(snap);
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
    const headers = createProjectIdentityHeaders({ 'Content-Type': 'application/json' });
    const body = withProjectIdentityPayload(
      (payload && typeof payload === 'object')
        ? { ...(payload as Record<string, unknown>) }
        : {},
    );

    const response = await fetch('/v1/chat/completions', {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok) {
      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent('agk:pin-required'));
      }
      if (response.status === 409) {
        const body = await response.json().catch(() => null) as {
          ok?: false;
          error?: string;
          detail?: string;
          conversation_id?: string;
          expected_revision?: number;
          current_revision?: number;
          correlation_id?: string;
        } | null;
        if (body && body.error === 'stale_conversation_revision') {
          throw new ConversationRevisionConflictError({
            ok: false,
            error: 'stale_conversation_revision',
            detail: body.detail || 'Conversation revision conflict',
            conversation_id: body.conversation_id || '',
            expected_revision: body.expected_revision ?? 0,
            current_revision: body.current_revision ?? 0,
            correlation_id: body.correlation_id,
          });
        }
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
      for (const frame of parsed.frames) {
        emitChatFrame(frame, handlers.onChunk, handlers.onConversationSnapshot);
      }
    }

    buffer += decoder.decode();
    const final = parseSseData(buffer, true);
    for (const frame of final.frames) {
      emitChatFrame(frame, handlers.onChunk, handlers.onConversationSnapshot);
    }
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
 * Unified Agent ask endpoint (Adaptive Stability & Ssak-Search Grounding).
 */
export async function askAgent(payload: AgentAskRequest): Promise<AgentAskResponse> {
  // F-43: `apiRequest`는 '/v1'을 앞에 붙인다 — 이 경로는 이미 '/api' namespace를 갖고 있으므로
  // `apiRequest`로 보내면 '/v1/api/agent/ask'(서버에 없음)가 된다. 전체 경로를 그대로 쓰는
  // `apiRequestPath`가 맞는 자리다.
  const raw = await apiRequestPath('/api/agent/ask', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return AgentAskResponseSchema.parse(raw);
}

/**
 * Fetch models list from backend.
 */
export async function fetchModels(): Promise<ModelInfo[]> {
  const raw = await apiRequest('/models');
  return ModelListResponseSchema.parse(raw).data;
}

export async function fetchLocalModels(refresh = false): Promise<LocalModelsResponse> {
  const path = `/api/models/local${refresh ? '?refresh=true' : ''}`;
  const raw = await requestJson(path, path);
  return LocalModelsResponseSchema.parse(raw);
}

/**
 * Load a local model into memory / runtime.
 */
export async function loadModel(modelId: string): Promise<{ ok: boolean; model?: string; status?: string; message?: string }> {
  const path = '/api/models/load';
  const raw = await requestJson(path, path, {
    method: 'POST',
    body: JSON.stringify({ model: modelId }),
  });
  return raw as { ok: boolean; model?: string; status?: string; message?: string };
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
 * MCP server health cache snapshot.
 */
export async function fetchMcpHealth(): Promise<McpHealthResponse> {
  const raw = await requestJson('/api/mcp/health', '/api/mcp/health', { suppressLog: true });
  return McpHealthResponseSchema.parse(raw);
}

/**
 * Probe configured MCP servers and refresh the health cache.
 */
export async function refreshMcpHealth(): Promise<McpHealthResponse> {
  const raw = await requestJson('/api/mcp/health/refresh', '/api/mcp/health/refresh', {
    method: 'POST',
    suppressLog: true,
  });
  return McpHealthResponseSchema.parse(raw);
}


/**
 * MCP OAuth connection status (no token values).
 */
export async function fetchMcpOAuthStatus(): Promise<McpOAuthStatusResponse> {
  const raw = await requestJson('/api/mcp/oauth/status', '/api/mcp/oauth/status', { suppressLog: true });
  return McpOAuthStatusResponseSchema.parse(raw);
}

/**
 * Start OAuth 2.1 authorization-code + PKCE for a configured MCP server.
 */
export async function startMcpOAuth(
  serverName: string,
  opts?: { clientId?: string; redirectUri?: string },
): Promise<McpOAuthStartResponse> {
  const raw = await requestJson('/api/mcp/oauth/start', '/api/mcp/oauth/start', {
    method: 'POST',
    body: JSON.stringify({
      server_name: serverName,
      client_id: opts?.clientId,
      redirect_uri: opts?.redirectUri,
    }),
  });
  return McpOAuthStartResponseSchema.parse(raw);
}

/**
 * Revoke stored MCP OAuth tokens for a server.
 */
export async function revokeMcpOAuth(serverName: string): Promise<{ ok: boolean; revoked?: boolean; connected?: boolean }> {
  const raw = await requestJson('/api/mcp/oauth/revoke', '/api/mcp/oauth/revoke', {
    method: 'POST',
    body: JSON.stringify({ server_name: serverName }),
  });
  return raw as { ok: boolean; revoked?: boolean; connected?: boolean };
}


/**
 * Fetch the session-limits disclosure shown before a session starts.
 * (freebuff benchmark: session limits + data-use notice before you start)
 */
export async function fetchSessionDisclosure(): Promise<SessionDisclosure> {
  const raw = await requestJson('/api/session/disclosure', '/api/session/disclosure');
  return SessionDisclosureSchema.parse(raw);
}

/**
 * Fetch the training recipe presets with their audited hyperparameter values.
 * (Phase 24: editable hyperparameter fields in the Studio training UI)
 */
export async function fetchTrainingRecipes(): Promise<TrainingRecipesResponse> {
  const raw = await requestJson('/api/recipes', '/api/recipes');
  return {
    ok: true,
    recipes: (Array.isArray((raw as { recipes?: unknown }).recipes) ? (raw as { recipes: unknown[] }).recipes : []).map(
      (r) => TrainingRecipeSchema.parse(r),
    ),
  };
}

/**
 * Start a real backend training job (Phase 59).
 *
 * Runs LoRAPipeline.apply_recipe with the edited hyperparameters, then
 * mlx-lm training, in a background thread; poll the returned job_id for
 * progress/loss/log tail.
 */
export interface TrainingJobStartPayload {
  recipe: string;
  base_model: string;
  source: string;
  platform: string;
  hyperparameters: Record<string, number | string>;
}

export interface TrainingJobView {
  job_id: string;
  status: 'running' | 'completed' | 'failed';
  recipe: string;
  platform: string;
  dataset_path: string;
  config_path: string;
  records: number;
  sufficient: boolean;
  progress: number;
  loss: number | null;
  log_tail: string[];
  error: string;
  started_at: number;
  finished_at: number | null;
}

export async function startTrainingJob(payload: TrainingJobStartPayload): Promise<{ ok: boolean; job_id: string }> {
  const raw = await requestJson('/api/training-jobs', '/api/training-jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  const parsed = raw as { ok?: boolean; job_id?: string };
  if (!parsed.job_id) throw new Error('training job start failed: no job_id');
  return { ok: parsed.ok === true, job_id: parsed.job_id };
}

export async function fetchTrainingJob(jobId: string): Promise<TrainingJobView> {
  return (await requestJson(`/api/training-jobs/${jobId}`, `/api/training-jobs/${jobId}`)) as TrainingJobView;
}

export async function cancelTrainingJob(jobId: string): Promise<{ ok: boolean; detail?: string }> {
  return (await requestJson(`/api/training-jobs/${jobId}/cancel`, `/api/training-jobs/${jobId}/cancel`, {
    method: 'POST',
  })) as { ok: boolean; detail?: string };
}

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

/**
 * CR-05: 명시적으로 선택한 API 키를 서버 `.env`에서 삭제한다.
 * 빈 입력(=유지)과 구분되는 경로이며, 삭제할 키 이름만 보낸다.
 */
export async function deleteSettingsKeys(keys: string[]): Promise<SettingsDeleteResponse> {
  const raw = await requestJson('/api/settings/env/delete', '/api/settings/env/delete', {
    method: 'POST',
    body: JSON.stringify(keys),
  });
  return SettingsDeleteResponseSchema.parse(raw);
}

/**
 * Authenticated PIN change (Settings). Uses the stored bearer via requestJson headers.
 * Never persists PIN values to browser storage.
 */
export async function changeAccessPin(currentPin: string, newPin: string): Promise<{ ok: boolean; detail: string }> {
  const raw = await requestJson('/api/auth/change-pin', '/api/auth/change-pin', {
    method: 'POST',
    body: JSON.stringify({ current_pin: currentPin, new_pin: newPin }),
  });
  if (
    typeof raw !== 'object'
    || raw === null
    || !('ok' in raw)
    || typeof (raw as { ok: unknown }).ok !== 'boolean'
  ) {
    throw new Error('Unexpected change-pin response.');
  }
  const detail =
    'detail' in raw && typeof (raw as { detail: unknown }).detail === 'string'
      ? (raw as { detail: string }).detail
      : 'PIN updated.';
  return { ok: (raw as { ok: boolean }).ok, detail };
}


/* ─── CTX-01 conversation revision protocol ───────────────── */

export type ConversationSnapshotWire = {
  conversation_id: string;
  project_id: string;
  revision: number;
  message_count: number;
  summary?: string | null;
  retained_message_ids?: string[];
  tokens_before?: number;
  tokens_after?: number;
  tokens_reduced?: number;
};

export type ConversationHistoryWire = {
  snapshot: ConversationSnapshotWire;
  messages: Array<{
    id: string;
    role: 'user' | 'assistant' | 'system' | 'tool';
    content: string;
    created_at: number;
    provenance?: string;
  }>;
  token_estimate: number;
};

export type ConversationConflictWire = {
  ok: false;
  error: 'stale_conversation_revision';
  detail: string;
  conversation_id: string;
  expected_revision: number;
  current_revision: number;
  correlation_id?: string;
};


async function parseConversationResponse<T>(response: Response): Promise<T> {
  if (response.status === 409) {
    const body = await response.json().catch(() => null) as ConversationConflictWire | null;
    if (body && body.error === 'stale_conversation_revision') {
      throw new ConversationRevisionConflictError(body);
    }
    const code = body && typeof body.error === 'string' ? body.error : 'conversation_conflict';
    throw new ConversationRequestError(`Conversation conflict (${response.status}): ${code}`, code, response.status);
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    let code = 'conversation_api_error';
    try {
      const parsed = JSON.parse(detail) as { error?: unknown };
      if (parsed && typeof parsed.error === 'string') code = parsed.error;
    } catch {
      // Non-JSON error body — keep the generic code.
    }
    // Prefix is asserted by e2e/tests/conversation-compaction.spec.ts.
    throw new ConversationRequestError(`Conversation API ${response.status}: ${code}`, code, response.status);
  }
  return await response.json() as T;
}

/** Fetch authoritative conversation projection (refresh/reconnect). */
export async function fetchConversationHistory(
  conversationId: string,
  projectId?: string | null,
): Promise<ConversationHistoryWire> {
  const headers = createProjectIdentityHeaders();
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
  const response = await fetch(`/v1/conversations/${encodeURIComponent(conversationId)}${qs}`, {
    method: 'GET',
    headers,
  });
  return parseConversationResponse<ConversationHistoryWire>(response);
}

/** CAS compact — returns summary, retained IDs, new revision, token delta. */
export async function compactConversation(payload: {
  conversation_id: string;
  expected_revision: number;
  project_id?: string;
  retain_tail?: number;
}): Promise<ConversationSnapshotWire> {
  const headers = createProjectIdentityHeaders({ 'Content-Type': 'application/json' });
  const body = withProjectIdentityPayload({ ...payload });
  const response = await fetch('/v1/conversations/compact', {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  return parseConversationResponse<ConversationSnapshotWire>(response);
}

/** CAS append a single turn (tests / recovery). */
export async function appendConversationTurn(payload: {
  conversation_id: string;
  expected_revision: number;
  role?: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  project_id?: string;
}): Promise<ConversationSnapshotWire> {
  const headers = createProjectIdentityHeaders({ 'Content-Type': 'application/json' });
  const body = withProjectIdentityPayload({ role: 'user', ...payload });
  const response = await fetch('/v1/conversations/append', {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  return parseConversationResponse<ConversationSnapshotWire>(response);
}

/** Fork conversation at a consistent revision. */
export async function forkConversation(payload: {
  conversation_id: string;
  expected_revision?: number;
  project_id?: string;
  new_conversation_id?: string;
}): Promise<ConversationSnapshotWire> {
  const headers = createProjectIdentityHeaders({ 'Content-Type': 'application/json' });
  const body = withProjectIdentityPayload({ ...payload });
  const response = await fetch('/v1/conversations/fork', {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  return parseConversationResponse<ConversationSnapshotWire>(response);
}
