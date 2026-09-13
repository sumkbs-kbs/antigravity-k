/**
 * useModalDialog 헬퍼 단위 테스트 (CR-08)
 * ========================================
 * focus 순환 범위와 배경 inert의 의미를 순수 함수 수준에서 고정한다.
 */

import { afterEach, describe, expect, it } from 'vitest';
import { getFocusableElements, inertBackgroundSiblings } from './useModalDialog';

function mount(html: string): HTMLElement {
  const host = document.createElement('div');
  host.innerHTML = html;
  document.body.appendChild(host);
  return host;
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('getFocusableElements', () => {
  it('DOM 순서대로 focus 가능한 요소만 모은다', () => {
    const host = mount(`
      <div id="dialog">
        <input id="first" />
        <a id="link" href="#x">link</a>
        <button id="disabled" disabled>disabled</button>
        <input id="hidden" type="hidden" />
        <button id="last">last</button>
        <div id="tabbable" tabindex="-1">skip</div>
      </div>
    `);
    const dialog = host.querySelector('#dialog') as HTMLElement;

    expect(getFocusableElements(dialog).map(el => el.id)).toEqual(['first', 'link', 'last']);
  });

  it('inert 또는 aria-hidden 하위 요소는 제외한다', () => {
    const host = mount(`
      <div id="dialog">
        <button id="ok">ok</button>
        <div inert><button id="inert-child">no</button></div>
        <div aria-hidden="true"><button id="hidden-child" aria-hidden="true">no</button></div>
      </div>
    `);
    const dialog = host.querySelector('#dialog') as HTMLElement;

    expect(getFocusableElements(dialog).map(el => el.id)).toEqual(['ok']);
  });
});

describe('inertBackgroundSiblings', () => {
  it('overlay의 형제만 inert로 만들고 해제 시 원상 복구한다', () => {
    const host = mount(`
      <div id="shell">
        <div id="background-1"><button>bg</button></div>
        <div id="overlay"><button>dialog</button></div>
        <div id="background-2"></div>
      </div>
    `);
    const overlay = host.querySelector('#overlay') as HTMLElement;

    const restore = inertBackgroundSiblings(overlay);

    expect(host.querySelector('#background-1')).toHaveAttribute('inert');
    expect(host.querySelector('#background-2')).toHaveAttribute('inert');
    expect(overlay).not.toHaveAttribute('inert');

    restore();

    expect(host.querySelector('#background-1')).not.toHaveAttribute('inert');
    expect(host.querySelector('#background-2')).not.toHaveAttribute('inert');
  });

  it('조상 체인을 따라 상위 레벨 형제도 inert로 만든다', () => {
    const host = mount(`
      <div id="shell">
        <div id="topbar"></div>
        <div id="layout">
          <div id="panel"></div>
          <div id="overlay"></div>
        </div>
      </div>
    `);
    const overlay = host.querySelector('#overlay') as HTMLElement;
    const outsider = document.createElement('div');
    outsider.id = 'outsider';
    document.body.appendChild(outsider);

    const restore = inertBackgroundSiblings(overlay);

    expect(host.querySelector('#panel'), '같은 레벨 형제').toHaveAttribute('inert');
    expect(host.querySelector('#topbar'), '상위 레벨 형제').toHaveAttribute('inert');
    expect(host.querySelector('#layout'), '경로상 조상은 inert가 아니어야 한다').not.toHaveAttribute('inert');
    expect(outsider, 'body의 자식은 건드리지 않는다').not.toHaveAttribute('inert');

    restore();

    expect(host.querySelector('#panel')).not.toHaveAttribute('inert');
    expect(host.querySelector('#topbar')).not.toHaveAttribute('inert');
  });

  it('이미 inert였던 형제는 해제하지 않는다', () => {
    const host = mount(`
      <div id="shell">
        <div id="already-inert" inert></div>
        <div id="overlay"></div>
      </div>
    `);
    const overlay = host.querySelector('#overlay') as HTMLElement;

    const restore = inertBackgroundSiblings(overlay);
    restore();

    expect(host.querySelector('#already-inert')).toHaveAttribute('inert');
  });

  it('부모가 없으면 아무것도 하지 않는다', () => {
    const orphan = document.createElement('div');
    expect(() => inertBackgroundSiblings(orphan)()).not.toThrow();
  });
});
