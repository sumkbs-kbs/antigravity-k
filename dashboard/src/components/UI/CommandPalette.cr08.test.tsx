/**
 * CommandPalette · CR-08 modal 계약
 * ==================================
 * BASELINE F04-b: "CommandPalette.tsx focus 초기화만, trap/복귀 계약 부족".
 *
 * 고정하는 계약:
 *  - C08-02: dialog가 modal 의미를 갖고(aria-modal), Tab/Shift+Tab이 안에서 순환하며,
 *            닫을 때 열기 직전 focus로 복귀하고, 열려 있는 동안 배경은 inert다.
 *  - C08-03: 방향키/Enter 동작과 한글 IME 조합 확정 Enter, 비동기 결과 경합을 보존한다.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

const commandSpy = vi.hoisted(() => ({
  alpha: vi.fn(),
  beta: vi.fn(),
  gamma: vi.fn(),
  note: vi.fn(),
}));

const searchSpy = vi.hoisted(() => ({ searchNoteCommands: vi.fn() }));

/*
 * 플러그인 명령 배열은 참조가 안정적이어야 한다 — 프로덕션의 usePluginCommands는
 * useMemo로 같은 배열을 돌려준다. 매 호출마다 새 배열을 주면 availableCommands →
 * getLocalMatches 참조가 매 렌더 바뀌어 결과 effect가 비동기 검색 결과를 되돌린다.
 */
const pluginSpy = vi.hoisted(() => ({ commands: [] as unknown[] }));

vi.mock('../../plugin/PluginManager', () => ({ usePluginCommands: () => pluginSpy.commands }));
vi.mock('../../features/command-palette/commandRegistry', () => {
  const commands = [
    { id: 'alpha', title: 'Alpha Command', subtitle: 'test', icon: 'search', keywords: ['alpha'], disabled: false, execute: commandSpy.alpha },
    { id: 'beta', title: 'Beta Command', subtitle: 'test', icon: 'note', keywords: ['beta'], disabled: false, execute: commandSpy.beta },
    { id: 'gamma', title: 'Gamma Command', subtitle: 'test', icon: 'chat', keywords: ['gamma'], disabled: false, execute: commandSpy.gamma },
  ];
  return {
    CommandSearchError: class CommandSearchError extends Error {},
    BUILTIN_COMMANDS: commands,
    filterPaletteCommands: (all: readonly unknown[], query: string) =>
      query.trim().length === 0
        ? all
        : all.filter((command) => JSON.stringify(command).toLowerCase().includes(query.toLowerCase())),
    searchNoteCommands: searchSpy.searchNoteCommands,
  };
});

import CommandPalette from './CommandPalette';
import { useUiStore } from '../../stores/uiStore';

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((innerResolve) => { resolve = innerResolve; });
  return { promise, resolve };
}

/** 팔레트를 셸(배경)과 같은 부모에 마운트한다 — 배경 inert 계약을 실제 구조로 검사하기 위해. */
function renderInShell(): { opener: HTMLButtonElement } {
  const opener = document.createElement('button');
  opener.textContent = 'shell action';
  document.body.appendChild(opener);
  const shell = document.createElement('div');
  shell.className = 'app-shell';
  document.body.appendChild(shell);

  render(
    <div className="app-shell">
      <div className="app-layout">
        <button type="button">background action</button>
      </div>
      <CommandPalette />
    </div>,
  );
  return { opener };
}

async function openPalette(): Promise<HTMLElement> {
  act(() => { useUiStore.setState({ commandPaletteVisible: true }); });
  const dialog = await screen.findByRole('dialog', { name: '명령 팔레트' });
  await waitFor(() => expect(screen.getByRole('combobox')).toHaveFocus());
  return dialog;
}

beforeEach(() => {
  searchSpy.searchNoteCommands.mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useUiStore.setState({ commandPaletteVisible: false });
  document.querySelectorAll('.app-shell').forEach(node => node.remove());
  document.querySelectorAll('button[data-cr08-opener]').forEach(node => node.remove());
});

describe('CommandPalette · CR-08 modal 계약', () => {
  it('dialog가 modal 의미(role=dialog, aria-modal)를 갖는다', async () => {
    renderInShell();
    const dialog = await openPalette();

    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAccessibleName('명령 팔레트');
  });

  it('열릴 때 검색 입력이 초기 focus를 받는다', async () => {
    renderInShell();
    await openPalette();

    expect(screen.getByRole('combobox')).toHaveFocus();
  });

  it('Tab이 마지막 항목에서 첫 요소로 순환한다', async () => {
    renderInShell();
    await openPalette();
    const first = screen.getByRole('combobox');
    const options = await screen.findAllByRole('option');
    const last = options[options.length - 1];

    (last as HTMLElement).focus();
    fireEvent.keyDown(last, { key: 'Tab' });

    expect(first).toHaveFocus();
  });

  it('Shift+Tab이 첫 요소에서 마지막 항목으로 순환한다', async () => {
    renderInShell();
    await openPalette();
    const first = screen.getByRole('combobox');
    const options = await screen.findAllByRole('option');
    const last = options[options.length - 1];

    first.focus();
    fireEvent.keyDown(first, { key: 'Tab', shiftKey: true });

    expect(last).toHaveFocus();
  });

  it('열려 있는 동안 배경(형제)이 inert가 되고 닫으면 원상 복구된다', async () => {
    renderInShell();
    await openPalette();

    const background = document.querySelector('.app-layout');
    expect(background).not.toBeNull();
    expect(background).toHaveAttribute('inert');

    act(() => { useUiStore.setState({ commandPaletteVisible: false }); });

    await waitFor(() => expect(background).not.toHaveAttribute('inert'));
  });

  it('Escape로 닫으면 열기 직전 focus로 복귀한다', async () => {
    renderInShell();
    const opener = document.createElement('button');
    opener.setAttribute('data-cr08-opener', 'true');
    document.body.appendChild(opener);
    opener.focus();
    expect(opener).toHaveFocus();

    await openPalette();
    expect(screen.getByRole('combobox')).toHaveFocus();

    fireEvent.keyDown(window, { key: 'Escape' });

    await waitFor(() => expect(opener).toHaveFocus());
  });

  it('Enter가 선택된 명령을 실행한다(조합 중이 아닐 때)', async () => {
    renderInShell();
    await openPalette();
    await screen.findAllByRole('option');

    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Enter', isComposing: false });

    expect(commandSpy.alpha).toHaveBeenCalledTimes(1);
    expect(commandSpy.beta).not.toHaveBeenCalled();
  });

  it('방향키가 선택을 옮기고 aria-activedescendant가 따라간다', async () => {
    renderInShell();
    await openPalette();
    await screen.findAllByRole('option');
    const input = screen.getByRole('combobox');

    expect(input).toHaveAttribute('aria-activedescendant', 'cmd-option-alpha');

    fireEvent.keyDown(input, { key: 'ArrowDown' });
    expect(input).toHaveAttribute('aria-activedescendant', 'cmd-option-beta');

    fireEvent.keyDown(input, { key: 'ArrowUp' });
    expect(input).toHaveAttribute('aria-activedescendant', 'cmd-option-alpha');

    fireEvent.keyDown(input, { key: 'ArrowUp' });
    expect(input).toHaveAttribute('aria-activedescendant', 'cmd-option-alpha');
  });

  it('한글 IME 조합 확정 Enter(isComposing)는 명령을 실행하지 않는다', async () => {
    renderInShell();
    await openPalette();
    await screen.findAllByRole('option');

    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Enter', isComposing: true });

    expect(commandSpy.alpha).not.toHaveBeenCalled();
    expect(useUiStore.getState().commandPaletteVisible).toBe(true);
  });

  it('legacy keyCode 229로 들어오는 조합 Enter도 실행하지 않는다', async () => {
    renderInShell();
    await openPalette();
    await screen.findAllByRole('option');

    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Enter', keyCode: 229 });

    expect(commandSpy.alpha).not.toHaveBeenCalled();
    expect(useUiStore.getState().commandPaletteVisible).toBe(true);
  });

  it('늦게 도착한 이전 검색 결과가 최신 결과를 덮어쓰지 않는다', async () => {
    const first = deferred<readonly unknown[]>();
    const second = deferred<readonly unknown[]>();
    searchSpy.searchNoteCommands.mockImplementation((query: string) =>
      query === 'alpha' ? first.promise : second.promise,
    );

    renderInShell();
    await openPalette();
    const input = screen.getByRole('combobox');

    fireEvent.change(input, { target: { value: 'alpha' } });
    await waitFor(() => expect(searchSpy.searchNoteCommands).toHaveBeenCalledWith('alpha'), { timeout: 2_000 });

    fireEvent.change(input, { target: { value: 'beta' } });
    await waitFor(() => expect(searchSpy.searchNoteCommands).toHaveBeenCalledWith('beta'), { timeout: 2_000 });

    // 이전(alpha) 검색이 나중에 도착해도 무시되어야 한다.
    await act(async () => {
      first.resolve([
        { id: 'note:alpha', title: 'STALE alpha note', subtitle: 'note', icon: 'note', keywords: [], disabled: false, execute: commandSpy.note },
      ]);
      await first.promise;
    });
    expect(screen.queryByText('STALE alpha note')).not.toBeInTheDocument();

    // 최신(beta) 검색 결과는 반영된다.
    await act(async () => {
      second.resolve([
        { id: 'note:beta', title: 'FRESH beta note', subtitle: 'note', icon: 'note', keywords: [], disabled: false, execute: commandSpy.note },
      ]);
      await second.promise;
    });
    expect(await screen.findByText('FRESH beta note')).toBeInTheDocument();
    expect(screen.queryByText('STALE alpha note')).not.toBeInTheDocument();
  });
});
