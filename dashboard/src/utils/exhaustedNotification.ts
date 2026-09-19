/**
 * exhaustedNotification — 세션 소진 브라우저 알림 (Phase 30)
 * ===========================================================
 * 세션 고지 등급이 처음 `exhausted`에 도달하면 OS 브라우저 알림을 발송한다.
 * - 미지원 환경(Notification 미정의)·거부(denied)·기본(default) 권한에서는 조용히 무시
 *   (알림은 비필수 UX — 요청 팝업을 띄우지 않는다. 사용자가 직접 허용한 경우만 동작)
 * - `tag`로 중복 방지: 같은 에피소드에서 이미 떠 있는 알림을 대체 (중복 적재 없음)
 * - 실제 발송 여부를 반환해 스토어에서 "이 에피소드에 알림했음" 표시에 사용
 */

export const EXHAUSTED_NOTIFICATION_TAG = 'session-exhausted';

export interface NotifyOptions {
  /** 예산 초과 안내 등 소진 원인 메시지 */
  message?: string;
  /** 클릭 시 이동할 SPA 경로 (기본 /settings) */
  targetPath?: string;
}

export function isNotificationSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window;
}

export function notifyExhausted(message: string, options: NotifyOptions = {}): boolean {
  if (!isNotificationSupported()) return false;
  if (typeof Notification === 'undefined') return false;
  if (Notification.permission !== 'granted') return false;

  const targetPath = options.targetPath ?? '/settings';
  try {
    const notification = new Notification('세션 한도 소진', {
      body: message,
      tag: EXHAUSTED_NOTIFICATION_TAG,
    });
    // 배너의 agk:pushstate와 동일한 SPA 라우팅 메커니즘 재사용
    // (NotificationOptions에 onclick이 없어 인스턴스에 할당)
    notification.onclick = () => {
      window.focus();
      window.dispatchEvent(new CustomEvent('agk:pushstate', { detail: targetPath }));
      notification.close();
    };
    return !!notification;
  } catch {
    return false;
  }
}
