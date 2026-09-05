import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  apiRequest,
  checkHealth,
  fetchCacheStats,
  fetchLogLevels,
  fetchModelOperations,
  fetchModels,
  fetchSettings,
  fetchSystemMetrics,
  saveSettings,
  setAllLogLevels,
  setDebugMode,
  setLogLevel,
  streamChatCompletion,
} from './client';

function streamingResponse(chunks: readonly string[]): Response {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  }), {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

function byteStreamingResponse(chunks: readonly Uint8Array[]): Response {
  return new Response(new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      controller.close();
    },
  }), {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

describe('shared API client', () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('PIN: preserves the model list URL, PIN header, and array result', async () => {
    window.sessionStorage.setItem('ag_access_token', 'test-token');
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      object: 'list',
      data: [{ id: 'model-a', role: 'coding' }],
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));

    await expect(fetchModels()).resolves.toEqual([{ id: 'model-a', role: 'coding' }]);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(url).toBe('/v1/models');
    expect(headers.get('Authorization')).toBe('Bearer test-token');
    expect(headers.get('Content-Type')).toBe('application/json');
  });

  it('health accepts an empty backend array returned before models are loaded', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      status: 'ok',
      backends: [],
      rag_index_files: 0,
      cov_active: false,
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));

    await expect(checkHealth()).resolves.toMatchObject({ status: 'ok', backends: [] });
  });

  it('PIN: preserves the 401 PIN-required event and HTTP error', async () => {
    const pinRequired = vi.fn();
    window.addEventListener('agk:pin-required', pinRequired);
    fetchMock.mockResolvedValue(new Response(null, {
      status: 401,
      statusText: 'Unauthorized',
    }));

    try {
      await expect(apiRequest('/protected', { suppressLog: true })).rejects.toThrow(
        'HTTP 401: Unauthorized',
      );
      expect(pinRequired).toHaveBeenCalledOnce();
    } finally {
      window.removeEventListener('agk:pin-required', pinRequired);
    }
  });

  it('settings requests use the shared status-checked client', async () => {
    window.sessionStorage.setItem('ag_access_token', 'test-token');
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({
      settings: { model: { name: 'model-a' } },
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({
      ok: true,
      updated: 2,
      message: 'saved',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

    await expect(fetchSettings()).resolves.toEqual({ model: { name: 'model-a' } });
    await expect(saveSettings({ default_model: 'model-a' })).resolves.toMatchObject({ ok: true, updated: 2 });

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/settings', expect.objectContaining({ headers: expect.any(Headers) }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/settings/env', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ default_model: 'model-a' }),
    }));
    const [, init] = fetchMock.mock.calls[0];
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer test-token');
  });

  it('settings requests reject malformed payloads and non-OK responses before parsing JSON', async () => {
    const malformedJson = vi.fn().mockResolvedValue({ settings: { model: { name: 42 } } });
    fetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: malformedJson } as unknown as Response);
    await expect(fetchSettings()).rejects.toBeDefined();
    expect(malformedJson).toHaveBeenCalledOnce();

    const failedJson = vi.fn().mockResolvedValue({ detail: 'unavailable' });
    fetchMock.mockResolvedValueOnce({ ok: false, status: 503, statusText: 'Unavailable', json: failedJson } as unknown as Response);
    await expect(saveSettings({ default_model: 'model-a' })).rejects.toThrow('HTTP 503: Unavailable');
    expect(failedJson).not.toHaveBeenCalled();
  });

  it.each([
    ['models', { data: [{ id: 42 }] }, () => fetchModels()],
    ['model operations', {}, () => fetchModelOperations()],
    ['health', {}, () => checkHealth()],
    ['system metrics', {}, () => fetchSystemMetrics()],
    ['cache stats', {}, () => fetchCacheStats()],
    ['log levels', {}, () => fetchLogLevels()],
    ['single log update', {}, () => setLogLevel('antigravity_k.api', 'INFO')],
    ['all log updates', {}, () => setAllLogLevels('INFO')],
    ['debug mode', {}, () => setDebugMode('enable')],
  ] satisfies ReadonlyArray<readonly [string, unknown, () => Promise<unknown>]>) (
    'RED: JSON rejects a malformed %s response',
    async (_name, invalidBody, invoke) => {
      fetchMock.mockResolvedValue(new Response(JSON.stringify(invalidBody), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }));

      await expect(invoke()).rejects.toBeDefined();
    },
  );

  it('RED: system auth sends the PIN and dispatches the 401 event', async () => {
    window.sessionStorage.setItem('ag_access_token', 'test-token');
    const pinRequired = vi.fn();
    window.addEventListener('agk:pin-required', pinRequired);
    fetchMock.mockResolvedValue(new Response(null, {
      status: 401,
      statusText: 'Unauthorized',
    }));

    try {
      await expect(fetchSystemMetrics()).rejects.toThrow('HTTP 401: Unauthorized');
      const [, init] = fetchMock.mock.calls[0];
      expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer test-token');
      expect(pinRequired).toHaveBeenCalledOnce();
    } finally {
      window.removeEventListener('agk:pin-required', pinRequired);
    }
  });

  it('RED: stream uses named handlers, PIN auth, and ordered chunks', async () => {
    window.sessionStorage.setItem('ag_access_token', 'test-token');
    fetchMock.mockResolvedValue(streamingResponse([
      'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n',
      'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n',
      'data: [DONE]\n',
    ]));
    const events: string[] = [];

    await streamChatCompletion(
      { model: 'model-a', messages: [], stream: true },
      {
        onChunk: (text) => events.push(`chunk:${text}`),
        onDone: () => events.push('done'),
        onError: (error) => events.push(`error:${error.message}`),
      },
    );

    const [, init] = fetchMock.mock.calls[0];
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer test-token');
    expect(events).toEqual(['chunk:Hel', 'chunk:lo', 'done']);
  });

  it('RED: stream delivers a final unterminated data frame', async () => {
    fetchMock.mockResolvedValue(streamingResponse([
      'data: {"choices":[{"delta":{"content":"tail"}}]}',
    ]));
    const chunks: string[] = [];
    const onDone = vi.fn();

    await streamChatCompletion(
      { model: 'model-a', messages: [], stream: true },
      {
        onChunk: (text) => chunks.push(text),
        onDone,
        onError: vi.fn(),
      },
    );

    expect(chunks).toEqual(['tail']);
    expect(onDone).toHaveBeenCalledOnce();
  });

  it('RED: stream reports a missing response body deliberately', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 200 }));
    const onError = vi.fn();

    await streamChatCompletion(
      { model: 'model-a', messages: [], stream: true },
      {
        onChunk: vi.fn(),
        onDone: vi.fn(),
        onError,
      },
    );

    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0][0]).toEqual(
      new Error('Chat completion stream returned no response body.'),
    );
  });

  it('RED: stream emits the PIN event before reporting a 401', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 401 }));
    const events: string[] = [];
    const onPinRequired = () => events.push('pin-required');
    window.addEventListener('agk:pin-required', onPinRequired);

    try {
      await streamChatCompletion(
        { model: 'model-a', messages: [], stream: true },
        {
          onChunk: vi.fn(),
          onDone: vi.fn(),
          onError: (error) => events.push(`error:${error.message}`),
        },
      );
      expect(events).toEqual(['pin-required', 'error:Server returned 401']);
    } finally {
      window.removeEventListener('agk:pin-required', onPinRequired);
    }
  });

  it('RED: stream treats abort as completion exactly once', async () => {
    fetchMock.mockRejectedValue(new DOMException('Aborted', 'AbortError'));
    const onDone = vi.fn();
    const onError = vi.fn();

    await streamChatCompletion(
      { model: 'model-a', messages: [], stream: true },
      { onChunk: vi.fn(), onDone, onError },
    );

    expect(onDone).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it('GREEN: JSON preserves every consumed success shape', async () => {
    const responses = [
      { object: 'list', data: [{ id: 'model-a', role: 'coding' }] },
      {
        provider_capabilities: {
          'model-a': {
            model: 'model-a',
            provider: 'ollama',
            is_local: true,
            runtime_status: 'available',
            native_tool_calling: 'supported',
            source: 'registry',
            long_context_plan: {
              strategy: 'native',
              retrieval_mode: 'native',
              native_attention_enabled: true,
              kv_cache_compression_enabled: true,
              kv_cache_mode: 'backend_managed',
              context_token_limit: 32768,
              candidate_pool: 12,
              rationale: 'verified native long-context capability',
            },
          },
        },
        quality_calibration: {
          enabled: true,
          eligible_models: ['model-a'],
          ineligible_models: [],
          operational_metrics: [{
            model: 'model-a',
            outcome_count: 2,
            task_success_rate: 1,
            tool_accuracy: 0.5,
            retry_rate: 0,
          }],
        },
      },
      { status: 'ok', version: '1.0', backends: {}, rag_index_files: 3, cov_active: false },
      { ok: true, status: 'online', memory_mb: 100, cpu_percent: 5, total_tokens: 7 },
      {
        ok: true,
        stats: {
          total_entries: 1,
          total_tags: 1,
          hits: 2,
          misses: 1,
          hit_ratio: 0.67,
          memory_estimate_kb: 4,
          entries: [{ key: 'k', ttl: 60, age: 1, remaining_ttl: 59, tags: ['t'], hits: 2 }],
        },
      },
      {
        ok: true,
        loggers: [{
          name: 'antigravity_k.api',
          level: 20,
          level_name: 'INFO',
          effective_level: 20,
          effective_level_name: 'INFO',
          handlers: 1,
        }],
        debug_mode: false,
        count: 1,
      },
      {
        ok: true,
        result: {
          name: 'antigravity_k.api',
          previous_level: 30,
          current_level: 20,
          previous_level_name: 'WARNING',
          current_level_name: 'INFO',
        },
      },
      {
        ok: true,
        result: {
          target_level: 20,
          target_level_name: 'INFO',
          updated_count: 1,
          loggers: [{
            name: 'antigravity_k.api',
            previous_level: 30,
            current_level: 20,
            previous_level_name: 'WARNING',
            current_level_name: 'INFO',
          }],
        },
      },
      {
        ok: true,
        debug_mode: true,
        result: { success: true, message: 'enabled', updated_count: 1 },
      },
    ] as const;
    for (const response of responses) {
      fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(response), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }));
    }

    await expect(fetchModels()).resolves.toEqual(responses[0].data);
    await expect(fetchModelOperations()).resolves.toEqual(responses[1]);
    await expect(checkHealth()).resolves.toEqual(responses[2]);
    await expect(fetchSystemMetrics()).resolves.toEqual(responses[3]);
    await expect(fetchCacheStats()).resolves.toEqual(responses[4]);
    await expect(fetchLogLevels()).resolves.toEqual(responses[5]);
    await expect(setLogLevel('antigravity_k.api', 'INFO')).resolves.toEqual(responses[6]);
    await expect(setAllLogLevels('INFO')).resolves.toEqual(responses[7]);
    await expect(setDebugMode('enable')).resolves.toEqual(responses[8]);
  });

  it('GREEN: stream ignores malformed frames and accepts multiline data', async () => {
    fetchMock.mockResolvedValue(streamingResponse([
      'data: {not-json}\n\n',
      'data: {"choices":[{"delta":\n',
      'data: {"content":"multi"}}]}\n\n',
      'data: {"choices":[{"delta":{"content":42}}]}\n\n',
    ]));
    const chunks: string[] = [];
    const onError = vi.fn();

    await streamChatCompletion(
      { model: 'model-a', messages: [], stream: true },
      { onChunk: (text) => chunks.push(text), onDone: vi.fn(), onError },
    );

    expect(chunks).toEqual(['multi']);
    expect(onError).not.toHaveBeenCalled();
  });

  it('GREEN: stream preserves split UTF-8 content', async () => {
    const encoded = new TextEncoder().encode(
      'data: {"choices":[{"delta":{"content":"한글"}}]}\n\n',
    );
    const firstKoreanByte = new TextEncoder().encode('한')[0];
    const koreanIndex = encoded.indexOf(firstKoreanByte);
    fetchMock.mockResolvedValue(byteStreamingResponse([
      encoded.slice(0, koreanIndex + 1),
      encoded.slice(koreanIndex + 1),
    ]));
    const chunks: string[] = [];

    await streamChatCompletion(
      { model: 'model-a', messages: [], stream: true },
      { onChunk: (text) => chunks.push(text), onDone: vi.fn(), onError: vi.fn() },
    );

    expect(chunks).toEqual(['한글']);
  });

  it('GREEN: stream reports a non-abort transport error once', async () => {
    fetchMock.mockRejectedValue(new Error('network down'));
    const onDone = vi.fn();
    const onError = vi.fn();

    await streamChatCompletion(
      { model: 'model-a', messages: [], stream: true },
      { onChunk: vi.fn(), onDone, onError },
    );

    expect(onDone).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledOnce();
    expect(onError).toHaveBeenCalledWith(new Error('network down'));
  });
});
