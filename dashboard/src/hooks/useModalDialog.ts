/**
 * useModalDialog — dialog의 modal 계약을 한 곳에서 보장한다
 * ==========================================================
 * CR-08 (BASELINE F04-b). 저장소에는 focus trap/배경 inert를 보장하는
 * 공용 dialog primitive가 없어(모든 모달이 각자 Escape와 초기 focus만 처리)
 * 최소 공용 훅으로 분리했다. 새 모달은 이 훅을 재사용한다.
 *
 * 이 훅이 보장하는 것:
 *  1. 열릴 때 초기 focus 이동(지정 요소 → 없으면 컨테이너의 첫 focusable).
 *  2. Tab / Shift+Tab이 컨테이너 안에서 순환(focus trap).
 *  3. 닫힐 때 열기 직전 focus 요소로 복귀(연결이 살아 있을 때만).
 *  4. 열려 있는 동안 overlay의 형제(배경)에 `inert`를 걸고, 닫힐 때 원상 복구.
 *
 * 이 훅이 다루지 않는 것: Escape 닫기(호출자/전역 단축키의 책임), 내용 스크롤 잠금.
 * `aria-modal="true"`는 호출자가 dialog 요소에 직접 지정한다.
 */

import { useEffect, type RefObject } from 'react';

/** `RefObject<HTMLDivElement | null>` 같은 구체 ref를 그대로 받기 위한 구조적 타입. */
interface ModalElementRef {
  readonly current: HTMLElement | null;
}

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

/** 컨테이너 안의 focusable 요소를 DOM 순서대로 반환한다. inert/aria-hidden 하위는 제외. */
export function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    element =>
      element.closest('[inert]') === null &&
      element.getAttribute('aria-hidden') !== 'true',
  );
}

/**
 * overlay가 아닌 배경 요소를 `inert`로 만들어 상호작용을 막는다.
 *
 * overlay에서 위로 올라가며 **경로상의 모든 형제**(조상 체인 전체)를 inert로 만든다.
 * 한 단계만 처리하면 팔레트 오버레이가 레이아웃 안쪽에 마운트되는 실제 구조에서
 * 상단 바·토스트 영역 같은 형제가 살아남는다(실브라우저에서 실측).
 * 해제 함수를 반환하며, 원래 inert였던 요소는 그대로 둔다. body의 자식은 건드리지 않는다.
 */
export function inertBackgroundSiblings(overlay: HTMLElement): () => void {
  const touched: Array<{ element: HTMLElement; wasInert: boolean }> = [];

  let pathNode: HTMLElement = overlay;
  let parent = overlay.parentElement;
  while (parent !== null && parent !== document.body) {
    for (const child of Array.from(parent.children)) {
      if (child === pathNode || !(child instanceof HTMLElement)) continue;
      touched.push({ element: child, wasInert: child.hasAttribute('inert') });
      child.setAttribute('inert', '');
    }
    pathNode = parent;
    parent = parent.parentElement;
  }

  return () => {
    touched.forEach(({ element, wasInert }) => {
      if (!wasInert) element.removeAttribute('inert');
    });
  };
}

export interface UseModalDialogOptions {
  /** true인 동안 modal 계약이 적용된다. */
  active: boolean;
  /** dialog/overlay 컨테이너. Tab 순환 범위이고, 이 요소의 형제가 배경이 된다. */
  containerRef: RefObject<HTMLElement | null> | ModalElementRef;
  /** 열릴 때 focus를 받을 요소. 없으면 컨테이너의 첫 focusable을 쓴다. */
  initialFocusRef?: RefObject<HTMLElement | null> | ModalElementRef;
}

export function useModalDialog({ active, containerRef, initialFocusRef }: UseModalDialogOptions): void {
  useEffect(() => {
    if (!active) return undefined;

    /* 1) 열기 전 focus을 기억한다 */
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    /* 2) 배경 inert */
    const restoreBackground = containerRef.current !== null
      ? inertBackgroundSiblings(containerRef.current)
      : () => undefined;

    /* 3) Tab 순환 */
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;
      const container = containerRef.current;
      if (container === null) return;
      const focusable = getFocusableElements(container);
      if (focusable.length === 0) {
        event.preventDefault();
        container.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const current = document.activeElement;
      const inside = current instanceof HTMLElement && container.contains(current);
      if (event.shiftKey) {
        if (!inside || current === first) {
          event.preventDefault();
          last.focus();
        }
        return;
      }
      if (!inside || current === last) {
        event.preventDefault();
        first.focus();
      }
    };

    // capture 단계로 등록해 컨테이너 내부 핸들러보다 먼저 순환을 확정한다.
    document.addEventListener('keydown', handleKeyDown, true);

    /* 4) 초기 focus (컨테이너가 마운트된 다음 tick) */
    const focusTimer = setTimeout(() => {
      const container = containerRef.current;
      const target =
        initialFocusRef?.current ??
        (container !== null ? getFocusableElements(container)[0] : undefined) ??
        container ??
        undefined;
      target?.focus();
    }, 0);

    return () => {
      clearTimeout(focusTimer);
      document.removeEventListener('keydown', handleKeyDown, true);
      /*
       * 순서가 중요하다: 배경 inert를 먼저 해제해야 한다. inert 하위 요소에 대한
       * focus()는 브라우저가 조용히 무시하므로, 반대로 하면 focus 복귀가 실패한다
       * (실브라우저 e2e에서 실측).
       */
      restoreBackground();
      if (previouslyFocused !== null && previouslyFocused.isConnected) previouslyFocused.focus();
    };
  }, [active, containerRef, initialFocusRef]);
}
