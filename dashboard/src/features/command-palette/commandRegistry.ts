import ky from 'ky';
import { z } from 'zod';

import { useUiStore } from '../../stores/uiStore';

export type CommandIconName =
  | 'automation'
  | 'chat'
  | 'note'
  | 'plugin'
  | 'search'
  | 'settings'
  | 'sync'
  | 'test'
  | 'warning';

export type PaletteCommand = Readonly<{
  id: string;
  title: string;
  subtitle: string | null;
  icon: CommandIconName;
  keywords: readonly string[];
  disabled: boolean;
  execute: () => void | Promise<void>;
}>;

const NoteSearchResponseSchema = z.object({
  semantic_results: z.array(z.object({
    id: z.string(),
    text: z.string(),
    metadata: z.object({ source: z.string().optional() }).optional(),
  })).default([]),
  keyword_results: z.array(z.string()).default([]),
});

export class CommandSearchError extends Error {
  readonly cause: Error;

  constructor(cause: Error) {
    super('Command palette note search failed.');
    this.name = 'CommandSearchError';
    this.cause = cause;
  }
}

function dispatchCommandEvent(name: string, detail?: unknown): void {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

async function syncVault(): Promise<void> {
  const addToast = useUiStore.getState().addToast;
  try {
    const payload = z.object({ ok: z.boolean(), commit: z.string().optional() }).parse(
      await ky.post('/api/vault/sync').json<unknown>(),
    );
    if (payload.ok) {
      addToast(`Vault 동기화 완료 (commit: ${payload.commit?.slice(0, 7) ?? 'N/A'})`, 'success');
      return;
    }
    addToast('Vault 동기화 실패', 'error');
  } catch (error) {
    if (error instanceof Error) {
      addToast(`Vault 동기화 오류: ${error.message}`, 'error');
      return;
    }
    throw error;
  }
}

export const BUILTIN_COMMANDS = [
  {
    id: 'search', title: 'Search Notes', subtitle: 'Knowledge', icon: 'search',
    keywords: ['notes', '검색'], disabled: false, execute: () => undefined,
  },
  {
    id: 'new_note', title: 'Create New Note', subtitle: 'Knowledge', icon: 'note',
    keywords: ['wiki', 'note'], disabled: false,
    execute: () => dispatchCommandEvent('agk:open-wiki-new'),
  },
  {
    id: 'chat', title: 'Open AI Chat', subtitle: 'Workspace', icon: 'chat',
    keywords: ['assistant', '대화'], disabled: false,
    execute: () => dispatchCommandEvent('agk:navigate', '/chat'),
  },
  {
    id: 'goal', title: 'Autonomous Goal (/goal)', subtitle: 'Agent', icon: 'automation',
    keywords: ['goal', 'agent'], disabled: false,
    execute: () => dispatchCommandEvent('agk:chat-slash', { text: '/goal ' }),
  },
  {
    id: 'agentic', title: 'Agentic Upgrade Radar (/agentic)', subtitle: 'Agent', icon: 'automation',
    keywords: ['upgrade', 'radar'], disabled: false,
    execute: () => dispatchCommandEvent('agk:chat-slash', { text: '/agentic ' }),
  },
  {
    id: 'mcp', title: 'MCP Upgrade Radar (/mcp)', subtitle: 'Agent', icon: 'plugin',
    keywords: ['tools', 'integration'], disabled: false,
    execute: () => dispatchCommandEvent('agk:chat-slash', { text: '/mcp ' }),
  },
  {
    id: 'capabilities', title: 'Autonomous Capabilities (/capabilities)', subtitle: 'Agent', icon: 'automation',
    keywords: ['capability', 'tools'], disabled: false,
    execute: () => dispatchCommandEvent('agk:chat-slash', { text: '/capabilities ' }),
  },
  {
    id: 'self', title: 'Self Capability Report (/self)', subtitle: 'Agent', icon: 'automation',
    keywords: ['report', 'self'], disabled: false,
    execute: () => dispatchCommandEvent('agk:chat-slash', { text: '/self' }),
  },
  {
    id: 'codex', title: 'Codex Capability Transfer (/codex)', subtitle: 'Agent', icon: 'automation',
    keywords: ['codex', 'transfer'], disabled: false,
    execute: () => dispatchCommandEvent('agk:chat-slash', { text: '/codex ' }),
  },
  {
    id: 'benchmark', title: 'Collective Benchmark Report (/benchmark)', subtitle: 'Evaluation', icon: 'test',
    keywords: ['benchmark', 'evaluation'], disabled: false,
    execute: () => dispatchCommandEvent('agk:chat-slash', { text: '/benchmark report' }),
  },
  {
    id: 'settings', title: 'Preferences', subtitle: 'Workspace', icon: 'settings',
    keywords: ['settings', '환경 설정'], disabled: false,
    execute: () => dispatchCommandEvent('agk:navigate', '/settings'),
  },
  {
    id: 'sync', title: 'Sync Vault (Git)', subtitle: 'Repository', icon: 'sync',
    keywords: ['git', 'vault'], disabled: false, execute: syncVault,
  },
  {
    id: 'selftest', title: 'Self-Test', subtitle: 'Evaluation', icon: 'test',
    keywords: ['diagnostics', 'test'], disabled: false,
    execute: () => useUiStore.getState().addToast('Self-test triggered', 'info'),
  },
  {
    id: 'tdd_loop', title: 'Test-Driven Code Generation', subtitle: 'Development', icon: 'test',
    keywords: ['tdd', 'test'], disabled: false,
    execute: () => useUiStore.getState().addToast('TDD 루프 생성 중...', 'info'),
  },
] as const satisfies readonly PaletteCommand[];

export function filterPaletteCommands(
  commands: readonly PaletteCommand[],
  query: string,
): readonly PaletteCommand[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (normalized.length === 0) return commands;
  return commands.filter((command) => [command.id, command.title, ...command.keywords]
    .some((value) => value.toLocaleLowerCase().includes(normalized)));
}

export async function searchNoteCommands(query: string): Promise<readonly PaletteCommand[]> {
  try {
    const response = NoteSearchResponseSchema.parse(
      await ky.get('/v1/notes/search', { searchParams: { q: query } }).json<unknown>(),
    );
    const semantic = response.semantic_results.map((result) => ({
      id: `note-semantic:${result.id}`,
      title: `${result.text.slice(0, 40)}${result.text.length > 40 ? '…' : ''}`,
      subtitle: 'Semantic match',
      icon: 'note',
      keywords: [result.id],
      disabled: false,
      execute: () => dispatchCommandEvent('agk:open-wiki-note', result.metadata?.source ?? result.id),
    } satisfies PaletteCommand));
    const keyword = response.keyword_results.map((path) => ({
      id: `note-keyword:${path}`,
      title: path,
      subtitle: 'Keyword match',
      icon: 'note',
      keywords: [path],
      disabled: false,
      execute: () => dispatchCommandEvent('agk:open-wiki-note', path),
    } satisfies PaletteCommand));
    return [...semantic, ...keyword];
  } catch (error) {
    if (error instanceof Error) throw new CommandSearchError(error);
    throw error;
  }
}
