/**
 * wikiStore Tests (Phase 54)
 * ==========================
 * Tests the Zustand wiki/vault store — state management, API actions,
 * localStorage integration, error handling, and edge cases.
 */

import { describe, it, expect, beforeEach, afterAll, vi } from 'vitest';
import { useWikiStore } from '../wikiStore';

beforeEach(() => {
  useWikiStore.setState({
    vaultPath: '',
    treeData: [],
    currentDoc: null,
    isEditing: false,
    editContent: '',
    searchQuery: '',
    searchResults: [],
    isLoading: false,
  });
  localStorage.clear();
});

afterAll(() => {
  vi.unstubAllGlobals();
});

describe('useWikiStore — initial state', () => {
  it('starts with default state', () => {
    const state = useWikiStore.getState();
    expect(state.vaultPath).toBe('');
    expect(state.treeData).toEqual([]);
    expect(state.currentDoc).toBeNull();
    expect(state.isEditing).toBe(false);
    expect(state.editContent).toBe('');
    expect(state.searchQuery).toBe('');
    expect(state.searchResults).toEqual([]);
    expect(state.isLoading).toBe(false);
  });
});

describe('useWikiStore — setters', () => {
  it('setVaultPath updates vaultPath', () => {
    useWikiStore.getState().setVaultPath('/test/vault');
    expect(useWikiStore.getState().vaultPath).toBe('/test/vault');
  });

  it('setTreeData updates treeData', () => {
    const tree = [{ name: 'doc.md', path: '/doc.md', type: 'file' as const }];
    useWikiStore.getState().setTreeData(tree);
    expect(useWikiStore.getState().treeData).toEqual(tree);
  });

  it('setCurrentDoc sets document and clears via null', () => {
    const doc = { path: '/test.md', content: '# Hello', metadata: {} };
    useWikiStore.getState().setCurrentDoc(doc);
    expect(useWikiStore.getState().currentDoc).toEqual(doc);

    useWikiStore.getState().setCurrentDoc(null);
    expect(useWikiStore.getState().currentDoc).toBeNull();
  });

  it('setIsEditing toggles editing state', () => {
    useWikiStore.getState().setIsEditing(true);
    expect(useWikiStore.getState().isEditing).toBe(true);
    useWikiStore.getState().setIsEditing(false);
    expect(useWikiStore.getState().isEditing).toBe(false);
  });

  it('setEditContent stores edit content', () => {
    useWikiStore.getState().setEditContent('new content');
    expect(useWikiStore.getState().editContent).toBe('new content');
  });

  it('setSearchQuery stores query', () => {
    useWikiStore.getState().setSearchQuery('hello');
    expect(useWikiStore.getState().searchQuery).toBe('hello');
  });

  it('setSearchResults stores results', () => {
    useWikiStore.getState().setSearchResults(['doc1.md', 'doc2.md']);
    expect(useWikiStore.getState().searchResults).toEqual(['doc1.md', 'doc2.md']);
  });

  it('setLoading toggles loading', () => {
    useWikiStore.getState().setLoading(true);
    expect(useWikiStore.getState().isLoading).toBe(true);
    useWikiStore.getState().setLoading(false);
    expect(useWikiStore.getState().isLoading).toBe(false);
  });
});

describe('useWikiStore — initVault', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('loads config when saved path exists in localStorage', async () => {
    localStorage.setItem('antigravity_vault_path', '/saved/vault');
    (global.fetch as any)
      .mockResolvedValueOnce({ json: () => Promise.resolve({ ok: true }) }) // POST config
      .mockResolvedValueOnce({ json: () => Promise.resolve({ ok: true, vault_path: '/saved/vault' }) }) // GET config
      .mockResolvedValueOnce({ json: () => Promise.resolve({ vault_path: '/saved/vault', tree: [] }) }); // loadTree

    await useWikiStore.getState().initVault();
    expect(useWikiStore.getState().vaultPath).toBe('/saved/vault');
    expect(localStorage.getItem('antigravity_vault_path')).toBe('/saved/vault');
  });

  it('handles POST config failure gracefully', async () => {
    localStorage.setItem('antigravity_vault_path', '/saved/vault');
    (global.fetch as any)
      .mockRejectedValueOnce(new Error('POST failed'))
      .mockResolvedValueOnce({ json: () => Promise.resolve({ ok: true, vault_path: '/saved/vault' }) })
      .mockResolvedValueOnce({ json: () => Promise.resolve({ vault_path: '/saved/vault', tree: [] }) });

    await useWikiStore.getState().initVault();
    expect(useWikiStore.getState().vaultPath).toBe('/saved/vault');
  });

  it('loads config without saved path', async () => {
    (global.fetch as any)
      .mockResolvedValueOnce({ json: () => Promise.resolve({ ok: true, vault_path: '/new/vault' }) })
      .mockResolvedValueOnce({ json: () => Promise.resolve({ vault_path: '/new/vault', tree: [] }) });

    await useWikiStore.getState().initVault();
    expect(useWikiStore.getState().vaultPath).toBe('/new/vault');
  });

  it('handles GET config failure gracefully', async () => {
    (global.fetch as any)
      .mockRejectedValueOnce(new Error('GET failed'))
      .mockResolvedValueOnce({ json: () => Promise.resolve({ ok: true }) });

    await useWikiStore.getState().initVault();
    // Should still have default vaultPath
    expect(useWikiStore.getState().vaultPath).toBe('');
  });
});

describe('useWikiStore — loadTree', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('loads tree data successfully', async () => {
    const tree = [
      { name: 'docs', path: '/docs', type: 'folder' as const, children: [] },
    ];
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve({ vault_path: '/vault', tree }),
    });

    await useWikiStore.getState().loadTree();
    expect(useWikiStore.getState().vaultPath).toBe('/vault');
    expect(useWikiStore.getState().treeData).toEqual(tree);
  });

  it('handles API error gracefully', async () => {
    (global.fetch as any).mockRejectedValue(new Error('Network error'));
    await useWikiStore.getState().loadTree();
    expect(useWikiStore.getState().treeData).toEqual([]);
  });
});

describe('useWikiStore — loadDocument', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('loads document successfully', async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ content: '# Hello', metadata: { title: 'Hello' } }),
    });

    await useWikiStore.getState().loadDocument('/test.md');
    const doc = useWikiStore.getState().currentDoc;
    expect(doc).not.toBeNull();
    expect(doc!.path).toBe('/test.md');
    expect(doc!.content).toBe('# Hello');
    expect(useWikiStore.getState().isEditing).toBe(false);
  });

  it('handles HTTP error gracefully', async () => {
    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({}),
    });

    await useWikiStore.getState().loadDocument('/missing.md');
    expect(useWikiStore.getState().currentDoc).toBeNull();
  });

  it('handles network error gracefully', async () => {
    (global.fetch as any).mockRejectedValue(new Error('Network error'));
    await useWikiStore.getState().loadDocument('/test.md');
    expect(useWikiStore.getState().currentDoc).toBeNull();
  });
});

describe('useWikiStore — saveDocument', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('saves document successfully', async () => {
    useWikiStore.getState().setCurrentDoc({ path: '/test.md', content: 'old', metadata: { title: 'Test' } });
    (global.fetch as any)
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) }) // POST write
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ content: 'new', metadata: {} }) }); // loadDocument

    const result = await useWikiStore.getState().saveDocument('/test.md', 'new content');
    expect(result).toBe(true);
    expect(useWikiStore.getState().isEditing).toBe(false);
  });

  it('returns false on HTTP error', async () => {
    (global.fetch as any).mockResolvedValue({ ok: false, status: 500 });
    const result = await useWikiStore.getState().saveDocument('/test.md', 'content');
    expect(result).toBe(false);
  });

  it('returns false on network error', async () => {
    (global.fetch as any).mockRejectedValue(new Error('Network error'));
    const result = await useWikiStore.getState().saveDocument('/test.md', 'content');
    expect(result).toBe(false);
  });

  it('uses existing metadata when not provided', async () => {
    const metadata = { title: 'Test' };
    useWikiStore.getState().setCurrentDoc({ path: '/test.md', content: 'old', metadata });
    (global.fetch as any)
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ content: 'new', metadata }) });

    await useWikiStore.getState().saveDocument('/test.md', 'new content');
    const callArgs = (global.fetch as any).mock.calls[0];
    const body = JSON.parse(callArgs[1].body);
    expect(body.metadata).toEqual(metadata);
  });
});

describe('useWikiStore — createDocument', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('creates document successfully', async () => {
    (global.fetch as any)
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) }) // POST write
      .mockResolvedValueOnce({ json: () => Promise.resolve({ tree: [] }) }) // loadTree
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ content: '', metadata: {} }) }); // loadDocument

    const result = await useWikiStore.getState().createDocument('/new.md', 'New Doc', ['docs']);
    expect(result).toBe(true);
  });

  it('returns false on HTTP error', async () => {
    (global.fetch as any).mockResolvedValue({ ok: false, status: 500 });
    const result = await useWikiStore.getState().createDocument('/new.md', 'New', []);
    expect(result).toBe(false);
  });
});

describe('useWikiStore — searchDocuments', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('searches and returns combined results', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve({
        keyword_results: ['doc1.md'],
        semantic_results: [{ metadata: { source: 'doc2.md' } }, { id: 'doc3.md' }],
      }),
    });

    await useWikiStore.getState().searchDocuments('hello');
    expect(useWikiStore.getState().searchResults).toEqual(['doc1.md', 'doc2.md', 'doc3.md']);
  });

  it('returns empty results for empty query and calls loadTree', async () => {
    const loadTreeSpy = vi.spyOn(useWikiStore.getState(), 'loadTree');
    await useWikiStore.getState().searchDocuments('');
    expect(useWikiStore.getState().searchResults).toEqual([]);
    expect(loadTreeSpy).toHaveBeenCalled();
  });

  it('handles API error gracefully', async () => {
    (global.fetch as any).mockRejectedValue(new Error('Search failed'));
    await useWikiStore.getState().searchDocuments('hello');
    expect(useWikiStore.getState().searchResults).toEqual([]);
  });

  it('handles API error with empty results', async () => {
    (global.fetch as any).mockRejectedValue(new Error('Search failed'));
    await useWikiStore.getState().searchDocuments('hello');
    expect(useWikiStore.getState().searchResults).toEqual([]);
  });

  it('deduplicates results with Set', async () => {
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve({
        keyword_results: ['doc1.md', 'doc2.md'],
        semantic_results: [{ metadata: { source: 'doc1.md' } }, { metadata: { source: 'doc2.md' } }],
      }),
    });

    await useWikiStore.getState().searchDocuments('hello');
    expect(useWikiStore.getState().searchResults).toEqual(['doc1.md', 'doc2.md']);
  });
});

describe('useWikiStore — updateVaultConfig', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('updates vault config successfully', async () => {
    (global.fetch as any)
      .mockResolvedValueOnce({ json: () => Promise.resolve({ ok: true, vault_path: '/new/vault' }) })
      .mockResolvedValueOnce({ json: () => Promise.resolve({ vault_path: '/new/vault', tree: [] }) });

    const result = await useWikiStore.getState().updateVaultConfig('/new/vault');
    expect(result).toBe(true);
    expect(useWikiStore.getState().vaultPath).toBe('/new/vault');
    expect(localStorage.getItem('antigravity_vault_path')).toBe('/new/vault');
    expect(useWikiStore.getState().currentDoc).toBeNull();
  });

  it('returns false when API returns not ok', async () => {
    (global.fetch as any).mockResolvedValue({ json: () => Promise.resolve({ ok: false }) });
    const result = await useWikiStore.getState().updateVaultConfig('/new/vault');
    expect(result).toBe(false);
  });

  it('returns false on network error', async () => {
    (global.fetch as any).mockRejectedValue(new Error('Network error'));
    const result = await useWikiStore.getState().updateVaultConfig('/new/vault');
    expect(result).toBe(false);
  });
});
