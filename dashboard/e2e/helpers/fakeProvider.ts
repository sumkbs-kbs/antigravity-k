/**
 * Fake provider — 제품이 **실제로 치는** provider 경로를 대신 응답하는 로컬 서버.
 *
 * 왜 필요한가
 * -----------
 * 브라우저 page.route 로 `/v1/chat/completions` 를 가로채면 **서버→provider 구간**이 사라진다.
 * 그러면 재는 대상이 "화면이 SSE 를 그리는가"로 줄어들고, provider 실패·부분 응답·취소가
 * **다른 질문**이 된다(가로챈 응답은 이미 완성된 문자열이다). 이 헬퍼는 그 구간을 **진짜로**
 * 남긴다: 제품 서버가 이 서버에 HTTP 를 치고, 이 서버가 실제 SSE 바이트를 흘린다.
 *
 * 표면
 * ----
 * - `POST /v1/chat/completions` — OpenAI 호환. `stream: true` 면 SSE, 아니면 JSON.
 * - `GET /v1/models` — OpenAI 호환 목록.
 * - `GET /api/tags`, `POST /api/chat`, `POST /api/generate` — Ollama 네이티브 표면(제품이
 *   엔진에 따라 이 경로를 친다).
 *
 * 재는 것은 **이 서버가 받은 것**(`hits`)이다 — 화면이 무엇을 보냈는지의 최종 기준이다.
 *
 * script 규칙: `replies` 는 **순서대로** 소비되고, 소진되면 `defaultText` 스트리밍으로 돌아간다
 * (fail-first 시나리오가 "두 번째 요청만 500" 같은 순서를 쓸 수 있어야 한다).
 */

import http from 'node:http';
import type { AddressInfo } from 'node:net';

export type FakeProviderReply =
  | { readonly kind: 'text'; readonly text: string; readonly delayMs?: number }
  | { readonly kind: 'status'; readonly status: number; readonly body?: string }
  /** 스트림 도중 연결을 끊는다 — 네트워크 드롭/부분 응답의 실제 모양. */
  | { readonly kind: 'abort'; readonly afterText?: string }
  /** 도구 호출 스트림 — 승인/도구 동선을 만들 때. */
  | { readonly kind: 'tool_call'; readonly name: string; readonly args: string };

export interface ProviderHit {
  readonly method: string;
  readonly path: string;
  readonly body: string;
}

export interface FakeProvider {
  /** `http://127.0.0.1:<port>` — 포트만. */
  readonly origin: string;
  /** `http://127.0.0.1:<port>/v1` — 제품 설정에 넣는 값. */
  readonly apiBase: string;
  readonly hits: ProviderHit[];
  readonly replies: FakeProviderReply[];
  stop: () => Promise<void>;
}

export interface FakeProviderOptions {
  readonly replies?: readonly FakeProviderReply[];
  readonly defaultText?: string;
}

function sseChunk(payload: unknown): string {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

function openAiDelta(text: string): string {
  return sseChunk({ id: 'chatcmpl-fake', object: 'chat.completion.chunk', choices: [{ index: 0, delta: { content: text } }] });
}

function openAiToolDelta(name: string, args: string): string {
  return sseChunk({
    id: 'chatcmpl-fake',
    object: 'chat.completion.chunk',
    choices: [{
      index: 0,
      delta: { tool_calls: [{ index: 0, id: 'call-fake-1', type: 'function', function: { name, arguments: args } }] },
      finish_reason: null,
    }],
  });
}

export async function startFakeProvider(options: FakeProviderOptions = {}): Promise<FakeProvider> {
  const hits: ProviderHit[] = [];
  const replies: FakeProviderReply[] = [...(options.replies ?? [])];
  const defaultText = options.defaultText ?? '가짜 provider 응답입니다.';

  const server = http.createServer((request, response) => {
    const chunks: Buffer[] = [];
    request.on('data', (chunk: Buffer) => chunks.push(chunk));
    request.on('end', () => {
      const body = Buffer.concat(chunks).toString('utf8');
      const path = request.url ?? '/';
      hits.push({ method: request.method ?? 'GET', path, body });

      const reply = replies.shift();

      // ── provider 장애를 **실제로** 만든다(status/abort) ──────────────────
      if (reply?.kind === 'status') {
        response.writeHead(reply.status, { 'content-type': 'application/json' });
        response.end(reply.body ?? JSON.stringify({ error: { message: 'fake provider failure' } }));
        return;
      }
      if (reply?.kind === 'abort') {
        response.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
        if (reply.afterText) response.write(openAiDelta(reply.afterText));
        // 헤더와 본문 일부만 보낸 채 소켓을 끊는다 = 네트워크 드롭.
        response.socket?.destroy();
        return;
      }

      if (path.startsWith('/api/tags')) {
        response.writeHead(200, { 'content-type': 'application/json' });
        response.end(JSON.stringify({ models: [{ name: 'fake-model-a', model: 'fake-model-a', size: 1 }] }));
        return;
      }
      if (path.startsWith('/v1/models')) {
        response.writeHead(200, { 'content-type': 'application/json' });
        response.end(JSON.stringify({
          object: 'list',
          data: [
            { id: 'fake-model-a', object: 'model' },
            { id: 'fake-model-b', object: 'model' },
          ],
        }));
        return;
      }

      let parsed: { stream?: unknown } = {};
      try {
        parsed = JSON.parse(body) as { stream?: unknown };
      } catch {
        parsed = {};
      }
      const streaming = parsed.stream === true || path.startsWith('/v1/chat/completions');

      if (reply?.kind === 'tool_call') {
        response.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
        response.write(openAiToolDelta(reply.name, reply.args));
        response.write(sseChunk({ choices: [{ index: 0, delta: {}, finish_reason: 'tool_calls' }] }));
        response.write('data: [DONE]\n\n');
        response.end();
        return;
      }

      const text = reply?.kind === 'text' ? reply.text : defaultText;
      const delayMs = reply?.kind === 'text' ? (reply.delayMs ?? 0) : 0;

      if (!streaming) {
        response.writeHead(200, { 'content-type': 'application/json' });
        response.end(JSON.stringify({
          id: 'chatcmpl-fake',
          object: 'chat.completion',
          choices: [{ index: 0, message: { role: 'assistant', content: text }, finish_reason: 'stop' }],
        }));
        return;
      }

      response.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
      const pieces = text.length > 1 ? [text.slice(0, text.length / 2), text.slice(text.length / 2)] : [text];
      const writeAll = (): void => {
        for (const piece of pieces) response.write(openAiDelta(piece));
        response.write(sseChunk({ choices: [{ index: 0, delta: {}, finish_reason: 'stop' }] }));
        response.write('data: [DONE]\n\n');
        response.end();
      };
      if (delayMs > 0) setTimeout(writeAll, delayMs);
      else writeAll();
    });
  });

  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address() as AddressInfo;
  const origin = `http://127.0.0.1:${address.port}`;

  return {
    origin,
    apiBase: `${origin}/v1`,
    hits,
    replies,
    stop: () => new Promise<void>((resolve, reject) => {
      server.closeAllConnections?.();
      server.close((error) => (error ? reject(error) : resolve()));
    }),
  };
}
