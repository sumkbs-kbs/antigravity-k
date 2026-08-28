/**
 * wikiStore Tests (Phase 54)
 * ==========================
 * Tests the Zustand wiki/vault store — state management, API actions,
 * localStorage integration, error handling, and edge cases.
 */

import { describe, it, expect, beforeEach, afterAll, vi, type Mock } from 'vitest';
import { useWikiStore } from '../wikiStore';

const jsonResponse = (body: unknown, init?: ResponseInit): Response =>
  new Response(JSON.stringify(body), {
    headers: { 'content-type': 'application/json' },
    ...init,
  });

let fetchMock: Mock<typeof fetch>;

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
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('loads config when saved path exists in localStorage', async () => {
    localStorage.setItem('antigravity_vault_path', '/saved/vault');
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ ok: true })) // POST config
      .mockResolvedValueOnce(jsonResponse({ ok: true, vault_path: '/saved/vault' })) // GET config
      .mockResolvedValueOnce(jsonResponse({ vault_path: '/saved/vault', tree: [] })); // loadTree

    await useWikiStore.getState().initVault();
    expect(useWikiStore.getState().vaultPath).toBe('/saved/vault');
    expect(localStorage.getItem('antigravity_vault_path')).toBe('/saved/vault');
  });

  it('handles POST config failure gracefully', async () => {
    localStorage.setItem('antigravity_vault_path', '/saved/vault');
    fetchMock
      .mockRejectedValueOnce(new Error('POST failed'))
      .mockResolvedValueOnce(jsonResponse({ ok: true, vault_path: '/saved/vault' }))
      .mockResolvedValueOnce(jsonResponse({ vault_path: '/saved/vault', tree: [] }));

    await useWikiStore.getState().initVault();
    expect(useWikiStore.getState().vaultPath).toBe('/saved/vault');
  });

  it('loads config without saved path', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ ok: true, vault_path: '/new/vault' }))
      .mockResolvedValueOnce(jsonResponse({ vault_path: '/new/vault', tree: [] }));

    await useWikiStore.getState().initVault();
    expect(useWikiStore.getState().vaultPath).toBe('/new/vault');
  });

  it('handles GET config failure gracefully', async () => {
    fetchMock
      .mockRejectedValueOnce(new Error('GET failed'))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));

    await useWikiStore.getState().initVault();
    // Should still have default vaultPath
    expect(useWikiStore.getState().vaultPath).toBe('');
  });
});

describe('useWikiStore — loadTree', () => {
  beforeEach(() => {
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('loads tree data successfully', async () => {
    const tree = [
      { name: 'docs', path: '/docs', type: 'folder' as const, children: [] },
    ];
    fetchMock.mockResolvedValue(jsonResponse({ vault_path: '/vault', tree }));

    await useWikiStore.getState().loadTree();
    expect(useWikiStore.getState().vaultPath).toBe('/vault');
    expect(useWikiStore.getState().treeData).toEqual(tree);
  });

  it('handles API error gracefully', async () => {
    fetchMock.mockRejectedValue(new Error('Network error'));
    await useWikiStore.getState().loadTree();
    expect(useWikiStore.getState().treeData).toEqual([]);
  });

  it('does not replace the tree when the API returns a non-OK response', async () => {
    const existingTree = [{ name: 'existing.md', path: '/existing.md', type: 'file' as const }];
    useWikiStore.getState().setTreeData(existingTree);
    const json = vi.fn();
    fetchMock.mockResolvedValue({ ok: false, status: 503, json } as unknown as Response);

    await useWikiStore.getState().loadTree();
    expect(useWikiStore.getState().treeData).toEqual(existingTree);
    expect(json).not.toHaveBeenCalled();
  });

  it('filters malformed tree entries at the API boundary', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      vault_path: '/vault',
      tree: [
        { name: 'valid.md', path: '/valid.md', type: 'file' },
        { name: 'invalid', path: '/invalid', type: 'unknown' },
      ],
    }));

    await useWikiStore.getState().loadTree();
    expect(useWikiStore.getState().treeData).toEqual([
      { name: 'valid.md', path: '/valid.md', type: 'file' },
    ]);
  });
});

describe('useWikiStore — loadDocument', () => {
  beforeEach(() => {
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('loads document successfully', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ content: '# Hello', metadata: { title: 'Hello' } }));

    await useWikiStore.getState().loadDocument('/test.md');
    const doc = useWikiStore.getState().currentDoc;
    expect(doc).not.toBeNull();
    expect(doc!.path).toBe('/test.md');
    expect(doc!.content).toBe('# Hello');
    expect(useWikiStore.getState().isEditing).toBe(false);
  });

  it('handles HTTP error gracefully', async () => {
    fetchMock.mockResolvedValue(jsonResponse({}, { status: 404 }));

    await useWikiStore.getState().loadDocument('/missing.md');
    expect(useWikiStore.getState().currentDoc).toBeNull();
  });

  it('handles network error gracefully', async () => {
    fetchMock.mockRejectedValue(new Error('Network error'));
    await useWikiStore.getState().loadDocument('/test.md');
    expect(useWikiStore.getState().currentDoc).toBeNull();
  });
});

describe('useWikiStore — saveDocument', () => {
  beforeEach(() => {
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('saves document successfully', async () => {
    useWikiStore.getState().setCurrentDoc({ path: '/test.md', content: 'old', metadata: { title: 'Test' } });
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ ok: true, path: '/test.md' })) // POST write
      .mockResolvedValueOnce(jsonResponse({ content: 'new', metadata: {} })); // loadDocument

    const result = await useWikiStore.getState().saveDocument('/test.md', 'new content');
    expect(result).toBe(true);
    expect(useWikiStore.getState().isEditing).toBe(false);
  });

  it('returns false on HTTP error', async () => {
    fetchMock.mockResolvedValue(jsonResponse({}, { status: 500 }));
    const result = await useWikiStore.getState().saveDocument('/test.md', 'content');
    expect(result).toBe(false);
  });

  it('returns false on network error', async () => {
    fetchMock.mockRejectedValue(new Error('Network error'));
    const result = await useWikiStore.getState().saveDocument('/test.md', 'content');
    expect(result).toBe(false);
  });

  it('returns false when the write response is not successful', async () => {
    useWikiStore.getState().setIsEditing(true);
    fetchMock.mockResolvedValue(jsonResponse({ ok: false, message: 'write failed' }));

    const result = await useWikiStore.getState().saveDocument('/test.md', 'content');
    expect(result).toBe(false);
    expect(useWikiStore.getState().isEditing).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('uses existing metadata when not provided', async () => {
    const metadata = { title: 'Test' };
    useWikiStore.getState().setCurrentDoc({ path: '/test.md', content: 'old', metadata });
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ ok: true, path: '/test.md' }))
      .mockResolvedValueOnce(jsonResponse({ content: 'new', metadata }));

    await useWikiStore.getState().saveDocument('/test.md', 'new content');
    const callArgs = fetchMock.mock.calls[0];
    expect(callArgs).toBeDefined();
    if (!callArgs) return;
    const requestInit = callArgs[1];
    expect(requestInit).toBeDefined();
    if (!requestInit) return;
    const body = JSON.parse(String(requestInit.body));
    expect(body.metadata).toEqual(metadata);
  });
});

describe('useWikiStore — createDocument', () => {
  beforeEach(() => {
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('creates document successfully', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ ok: true, path: '/new.md' })) // POST write
      .mockResolvedValueOnce(jsonResponse({ tree: [] })) // loadTree
      .mockResolvedValueOnce(jsonResponse({ content: '', metadata: {} })); // loadDocument

    const result = await useWikiStore.getState().createDocument('/new.md', 'New Doc', ['docs']);
    expect(result).toBe(true);
  });

  it('returns false on HTTP error', async () => {
    fetchMock.mockResolvedValue(jsonResponse({}, { status: 500 }));
    const result = await useWikiStore.getState().createDocument('/new.md', 'New', []);
    expect(result).toBe(false);
  });
});

describe('useWikiStore — searchDocuments', () => {
  beforeEach(() => {
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('searches and returns combined results', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      keyword_results: ['doc1.md'],
      semantic_results: [{ metadata: { source: 'doc2.md' } }, { id: 'doc3.md' }],
    }));

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
    fetchMock.mockRejectedValue(new Error('Search failed'));
    await useWikiStore.getState().searchDocuments('hello');
    expect(useWikiStore.getState().searchResults).toEqual([]);
  });

  it('returns empty results without parsing a non-OK response', async () => {
    useWikiStore.getState().setSearchResults(['stale.md']);
    const json = vi.fn();
    fetchMock.mockResolvedValue({ ok: false, status: 502, json } as unknown as Response);

    await useWikiStore.getState().searchDocuments('hello');
    expect(useWikiStore.getState().searchResults).toEqual([]);
    expect(json).not.toHaveBeenCalled();
  });

  it('handles API error with empty results', async () => {
    fetchMock.mockRejectedValue(new Error('Search failed'));
    await useWikiStore.getState().searchDocuments('hello');
    expect(useWikiStore.getState().searchResults).toEqual([]);
  });

  it('deduplicates results with Set', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      keyword_results: ['doc1.md', 'doc2.md'],
      semantic_results: [{ metadata: { source: 'doc1.md' } }, { metadata: { source: 'doc2.md' } }],
    }));

    await useWikiStore.getState().searchDocuments('hello');
    expect(useWikiStore.getState().searchResults).toEqual(['doc1.md', 'doc2.md']);
  });
});

describe('useWikiStore — updateVaultConfig', () => {
  beforeEach(() => {
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('updates vault config successfully', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ ok: true, vault_path: '/new/vault' }))
      .mockResolvedValueOnce(jsonResponse({ vault_path: '/new/vault', tree: [] }));

    const result = await useWikiStore.getState().updateVaultConfig('/new/vault');
    expect(result).toBe(true);
    expect(useWikiStore.getState().vaultPath).toBe('/new/vault');
    expect(localStorage.getItem('antigravity_vault_path')).toBe('/new/vault');
    expect(useWikiStore.getState().currentDoc).toBeNull();
  });

  it('returns false when API returns not ok', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: false }));
    const result = await useWikiStore.getState().updateVaultConfig('/new/vault');
    expect(result).toBe(false);
  });

  it('returns false on network error', async () => {
    fetchMock.mockRejectedValue(new Error('Network error'));
    const result = await useWikiStore.getState().updateVaultConfig('/new/vault');
    expect(result).toBe(false);
  });
});
