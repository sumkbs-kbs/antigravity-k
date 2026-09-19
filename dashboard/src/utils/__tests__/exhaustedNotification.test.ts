/**
 * exhaustedNotification Tests (Phase 30)
 * =======================================
 * Notification stub으로 권한/미지원/거부 분기와 tag·onclick 동작을 검증한다.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import {
  EXHAUSTED_NOTIFICATION_TAG,
  isNotificationSupported,
  notifyExhausted,
} from '../exhaustedNotification';

type Ctor = new (title: string, options?: Record<string, unknown>) => Record<string, unknown>;

let lastInstance: Record<string, unknown> | null = null;
let ctorSpy: ReturnType<typeof vi.fn> | null = null;

function installNotification(permission: string): void {
  ctorSpy = vi.fn(function (this: unknown, title: string, options?: Record<string, unknown>) {
    lastInstance = { title, ...options, close: vi.fn() };
    return lastInstance;
  }) as unknown as ReturnType<typeof vi.fn>;
  (window as unknown as { Notification: Ctor }).Notification = ctorSpy as unknown as Ctor;
  (window.Notification as unknown as { permission: string }).permission = permission;
}

function uninstallNotification(): void {
  delete (window as unknown as { Notification?: unknown }).Notification;
  lastInstance = null;
  ctorSpy = null;
}

describe('exhaustedNotification', () => {
  afterEach(() => {
    uninstallNotification();
    vi.restoreAllMocks();
  });

  it('reports unsupported when Notification is missing', () => {
    expect(isNotificationSupported()).toBe(false);
    expect(notifyExhausted('메시지')).toBe(false);
  });

  it('does nothing when permission is denied or default', () => {
    installNotification('denied');
    expect(notifyExhausted('메시지')).toBe(false);
    expect(ctorSpy).not.toHaveBeenCalled();

    installNotification('default');
    expect(notifyExhausted('메시지')).toBe(false);
    expect(ctorSpy).not.toHaveBeenCalled();
  });

  it('creates a tagged notification when permission is granted', () => {
    installNotification('granted');
    const sent = notifyExhausted('일일 예산이 소진되었습니다.');
    expect(sent).toBe(true);
    expect(ctorSpy).toHaveBeenCalledTimes(1);
    expect(lastInstance?.title).toBe('세션 한도 소진');
    expect(lastInstance?.body).toBe('일일 예산이 소진되었습니다.');
    expect(lastInstance?.tag).toBe(EXHAUSTED_NOTIFICATION_TAG);
  });

  it('onclick focuses the window and routes via agk:pushstate', () => {
    installNotification('granted');
    notifyExhausted('메시지', { targetPath: '/models' });

    const focusSpy = vi.spyOn(window, 'focus').mockImplementation(() => {});
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    const onClick = lastInstance?.onclick as () => void;
    onClick();

    expect(focusSpy).toHaveBeenCalledTimes(1);
    const event = dispatchSpy.mock.calls.map(([e]) => e).find(
      (e) => e instanceof CustomEvent,
    ) as CustomEvent | undefined;
    expect(event?.type).toBe('agk:pushstate');
    expect(event?.detail).toBe('/models');
    expect(lastInstance?.close).toBeTypeOf('function');
    focusSpy.mockRestore();
  });

  it('returns false instead of throwing when the constructor fails', () => {
    installNotification('granted');
    (window.Notification as unknown as Ctor) = function () {
      throw new Error('ctor boom');
    } as unknown as Ctor;
    expect(notifyExhausted('메시지')).toBe(false);
  });
});
