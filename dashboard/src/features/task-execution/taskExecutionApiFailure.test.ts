import { beforeEach, describe, expect, it, vi } from 'vitest';

const postMock = vi.hoisted(() => vi.fn());

vi.mock('ky', () => {
  class HTTPError extends Error {
    response: Response;

    constructor(response: Response) {
      super(`Request failed with status code ${response.status}`);
      this.name = 'HTTPError';
      this.response = response;
    }
  }

  return { default: { post: postMock }, HTTPError };
});

import { cancelTask, resumeTask } from './taskExecutionApi';
import { TaskIdSchema } from './taskExecutionSchema';

const taskId = TaskIdSchema.parse('task-owned-elsewhere');

// 모킹된 모듈의 HTTPError 로 실패를 만든다 — 제품 코드는 `instanceof HTTPError` 로 분기한다.
const mockedKy = (await import('ky')) as unknown as {
  HTTPError: new (response: Response) => Error;
};

function httpFailure(status: number, body: unknown): Error {
  return new mockedKy.HTTPError(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json' },
    }),
  );
}

/** 제품 코드는 `ky.post(...).json()` 을 부른다 — 모의도 **그 형태**를 돌려줘야 한다. */
function postResult(json: () => Promise<unknown>): { json: () => Promise<unknown> } {
  return { json };
}

beforeEach(() => {
  postMock.mockReset();
});

describe('cancelTask failure reporting (F-35)', () => {
  it('resolves when the server cancels the task', async () => {
    postMock.mockReturnValue(postResult(() => Promise.resolve({ status: 'cancelled', task_id: taskId })));

    await expect(cancelTask(taskId)).resolves.toBeUndefined();
  });

  it("surfaces the server's reason when another live process owns the task", async () => {
    const detail = "Another live process owns this task's execution — cancel it there";
    postMock.mockReturnValue(postResult(() => Promise.reject(httpFailure(409, { detail }))));

    // 화면이 "HTTP 409" 가 아니라 **사유**를 말해야 사용자가 다음 행동을 알 수 있다.
    await expect(cancelTask(taskId)).rejects.toThrow(detail);
  });

  it('keeps the original failure when the server gives no reason', async () => {
    postMock.mockReturnValue(postResult(() => Promise.reject(httpFailure(500, {}))));

    await expect(cancelTask(taskId)).rejects.toThrow(/status code 500/);
  });

  it('keeps non-HTTP failures untouched', async () => {
    postMock.mockReturnValue(postResult(() => Promise.reject(new Error('network down'))));

    await expect(resumeTask(taskId)).rejects.toThrow('network down');
  });
});
