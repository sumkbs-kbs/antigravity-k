import { afterEach, describe, expect, it, vi } from 'vitest';

import { BUILTIN_COMMANDS, filterPaletteCommands } from './commandRegistry';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('typed command registry', () => {
  it('keeps command identifiers unique and searches id, title, and keywords', () => {
    expect(new Set(BUILTIN_COMMANDS.map((command) => command.id)).size).toBe(BUILTIN_COMMANDS.length);
    expect(filterPaletteCommands(BUILTIN_COMMANDS, 'benchmark').map((command) => command.id)).toEqual([
      'benchmark',
    ]);
    expect(filterPaletteCommands(BUILTIN_COMMANDS, '환경 설정').map((command) => command.id)).toEqual([
      'settings',
    ]);
    expect(filterPaletteCommands(BUILTIN_COMMANDS, '작업').map((command) => command.id)).toEqual([
      'job_operations',
    ]);
  });

  it('navigates to the job operations console', async () => {
    const dispatch = vi.spyOn(window, 'dispatchEvent');
    const command = BUILTIN_COMMANDS.find((candidate) => candidate.id === 'job_operations');
    if (command === undefined) throw new TypeError('Job operations command fixture is missing.');

    await command.execute();

    const emitted = dispatch.mock.calls[0]?.[0];
    if (!(emitted instanceof CustomEvent)) throw new TypeError('Expected a custom browser event.');
    expect(emitted.type).toBe('agk:navigate');
    expect(emitted.detail).toBe('/plugins/job-operations');
  });

  it('executes a slash command through its typed browser event contract', async () => {
    const dispatch = vi.spyOn(window, 'dispatchEvent');
    const command = BUILTIN_COMMANDS.find((candidate) => candidate.id === 'goal');
    if (command === undefined) throw new TypeError('Goal command fixture is missing.');

    await command.execute();

    const emitted = dispatch.mock.calls[0]?.[0];
    if (!(emitted instanceof CustomEvent)) throw new TypeError('Expected a custom browser event.');
    expect(emitted.type).toBe('agk:chat-slash');
    expect(emitted.detail).toEqual({ text: '/goal ' });
  });
});
