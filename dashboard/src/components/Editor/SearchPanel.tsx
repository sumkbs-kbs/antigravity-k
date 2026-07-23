/**
 * SearchPanel — VS Code-style search & replace in files (Cmd+Shift+F)
 * =====================================================================
 * Full-text search with regex support, replace in files (single + batch),
 * result navigation (up/down arrows), and click-to-navigate matches.
 */

import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useEditorStore } from '../../stores/editorStore';
import { useUiStore } from '../../stores/uiStore';
import { getFileIcon } from '../../utils/fileIcons';

/* ─── Types ───────────────────────────────────────────────── */

interface SearchMatch {
  line: number;
  content: string;
}

interface SearchResult {
  file_path: string;
  file_name: string;
  matches: SearchMatch[];
  match_count: number;
}

interface SearchResponse {
  ok: boolean;
  query: string;
  results: SearchResult[];
  total_files: number;
  total_matches: number;
}

/* ─── Highlight match in text ─────────────────────────────── */

function highlightText(text: string, query: string, useRegex: boolean): React.ReactNode {
  if (!query || !text) return text;
  try {
    const flags = 'gi';
    const pattern = useRegex ? query : query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${pattern})`, flags);
    const parts = text.split(regex);
    if (parts.length === 1) return text;
    return parts.map((part, i) =>
      regex.test(part)
        ? <span key={i} style={{ background: 'rgba(255,183,77,0.3)', color: '#ffb74d', borderRadius: 2, padding: '0 1px' }}>{part}</span>
        : part
    );
  } catch {
    return text;
  }
}

/* ─── FileResult Component ─────────────────────────────────── */

interface FileResultProps {
  result: SearchResult;
  query: string;
  useRegex: boolean;
  replaceText: string;
  onOpenMatch: (filePath: string, line: number) => void;
  onReplaceSingle: (filePath: string, line: number, content: string) => void;
  onReplaceAllInFile: (filePath: string) => void;
  isFocused: boolean;
  focusedMatchKey: string | null;
}

const FileResult: React.FC<FileResultProps> = ({
  result, query, useRegex, replaceText,
  onOpenMatch, onReplaceSingle, onReplaceAllInFile,
  isFocused, focusedMatchKey,
}) => {
  const [expanded, setExpanded] = useState(true);
  const { addToast } = useUiStore();

  const handleReplaceLine = useCallback((match: SearchMatch) => {
    if (!replaceText.trim()) {
      addToast('바꿀 내용을 입력하세요', 'info');
      return;
    }
    onReplaceSingle(result.file_path, match.line, match.content);
  }, [replaceText, result.file_path, onReplaceSingle, addToast]);

  return (
    <div className={`search-file-group ${isFocused ? 'focused' : ''}`}>
      {/* File header */}
      <div
        className="search-file-header"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="search-collapse-icon">{expanded ? '▼' : '▶'}</span>
        <span className="search-file-icon">{getFileIcon(result.file_name)}</span>
        <span className="search-file-name">{result.file_name}</span>
        <span className="search-file-count">{result.match_count}</span>
        {replaceText.trim() && result.match_count > 0 && (
          <button
            className="search-replace-all-btn"
            onClick={e => { e.stopPropagation(); onReplaceAllInFile(result.file_path); }}
            title="Replace all in this file"
          >
            ↻ All
          </button>
        )}
      </div>

      {/* Matches list */}
      {expanded && (
        <div className="search-match-list">
          {result.matches.map((match, i) => {
            const matchKey = `${result.file_path}:${match.line}`;
            const isMatchFocused = focusedMatchKey === matchKey;
            return (
              <div
                key={i}
                className={`search-match-line ${isMatchFocused ? 'focused' : ''}`}
                onClick={() => onOpenMatch(result.file_path, match.line)}
              >
                <span className="search-match-line-no">{match.line}</span>
                <span className="search-match-text">
                  {highlightText(match.content.trim(), query, useRegex)}
                </span>
                {replaceText.trim() && (
                  <button
                    className="search-replace-btn"
                    onClick={e => { e.stopPropagation(); handleReplaceLine(match); }}
                    title="Replace this match"
                  >
                    Replace
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

/* ─── SearchPanel Component ────────────────────────────────── */

interface SearchPanelProps {
  visible: boolean;
  onClose: () => void;
}

const SearchPanel: React.FC<SearchPanelProps> = ({ visible, onClose }) => {
  const [query, setQuery] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [useRegex, setUseRegex] = useState(false);
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [totalFiles, setTotalFiles] = useState(0);
  const [totalMatches, setTotalMatches] = useState(0);
  const [searching, setSearching] = useState(false);
  const [replacing, setReplacing] = useState(false);
  const [searched, setSearched] = useState(false);
  const [focusedIdx, setFocusedIdx] = useState(-1);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const { openFile, updateFileContent } = useEditorStore();
  const { addToast } = useUiStore();

  // Flatten all matches for keyboard navigation
  const flatMatches = useMemo(() => {
    const list: Array<{ filePath: string; fileName: string; line: number; content: string }> = [];
    for (const r of results) {
      for (const m of r.matches) {
        list.push({ filePath: r.file_path, fileName: r.file_name, line: m.line, content: m.content });
      }
    }
    return list;
  }, [results]);

  // Focus input when panel becomes visible
  useEffect(() => {
    if (visible && searchInputRef.current) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }
    if (!visible) {
      setQuery('');
      setReplaceText('');
      setResults([]);
      setSearched(false);
      setFocusedIdx(-1);
    }
  }, [visible]);

  // Scroll focused match into view
  useEffect(() => {
    if (focusedIdx >= 0 && resultsRef.current) {
      const focusedEl = resultsRef.current.querySelector('.search-match-line.focused') as HTMLElement;
      focusedEl?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [focusedIdx]);

  const handleSearch = useCallback(async (q: string, regex?: boolean, cs?: boolean) => {
    const useR = regex ?? useRegex;
    const useCS = cs ?? caseSensitive;
    const trimmed = q.trim();
    if (trimmed.length < 1) {
      setResults([]);
      setSearched(false);
      return;
    }

    // Validate regex
    if (useR) {
      try { new RegExp(trimmed, useCS ? 'g' : 'gi'); } catch {
        setResults([]);
        setSearched(true);
        return;
      }
    }

    setSearching(true);
    setSearched(true);
    setFocusedIdx(-1);
    try {
      const res = await fetch('/api/fs/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: trimmed,
          max_results: 200,
          regex: useR,
          case_sensitive: useCS,
        }),
      });
      const data: SearchResponse = await res.json();
      if (data.ok) {
        setResults(data.results);
        setTotalFiles(data.total_files);
        setTotalMatches(data.total_matches);
      } else {
        setResults([]);
      }
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, [useRegex, caseSensitive]);

  // Debounced search on input change
  const handleInputChange = useCallback((value: string) => {
    setQuery(value);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(() => handleSearch(value), 300);
  }, [handleSearch]);

  const handleOpenMatch = useCallback(async (filePath: string, line: number) => {
    try {
      const res = await fetch(`/api/fs/read?file=${encodeURIComponent(filePath)}`);
      const data = await res.json();
      if (data.content !== undefined) {
        const fileName = filePath.split('/').pop() || filePath;
        openFile(filePath, fileName, data.content);
        addToast(`🔍 ${fileName}:${line}`, 'success');
      }
    } catch (err: any) {
      addToast(`파일 열기 오류: ${err.message}`, 'error');
    }
  }, [openFile, addToast]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      if (replaceText) { setReplaceText(''); return; }
      if (query) { setQuery(''); setResults([]); setSearched(false); return; }
      onClose();
    }
    if (e.key === 'Enter' && e.shiftKey) {
      e.preventDefault();
      handleSearch(query);
    }
    // Navigation: up/down arrows
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setFocusedIdx(prev => Math.min(prev + 1, flatMatches.length - 1));
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setFocusedIdx(prev => Math.max(prev - 1, 0));
    }
    // Open focused match
    if (e.key === 'Enter' && focusedIdx >= 0 && flatMatches[focusedIdx]) {
      e.preventDefault();
      const m = flatMatches[focusedIdx];
      handleOpenMatch(m.filePath, m.line);
    }
  }, [onClose, handleSearch, query, replaceText, flatMatches, focusedIdx, handleOpenMatch]);

  // Replace single match
  const handleReplaceSingle = useCallback(async (filePath: string, line: number, oldContent: string) => {
    if (!replaceText.trim() || replacing) return;
    setReplacing(true);
    try {
      // Read current file content
      const res = await fetch(`/api/fs/read?file=${encodeURIComponent(filePath)}`);
      const data = await res.json();
      if (data.content === undefined) throw new Error('Cannot read file');

      const lines = data.content.split('\n');
      const idx = line - 1;
      if (idx < 0 || idx >= lines.length) throw new Error('Line out of range');

      // Replace the matched line
      const oldLine = lines[idx];
      let newLine: string;
      const flags = caseSensitive ? 'g' : 'gi';
      try {
        const pattern = useRegex ? new RegExp(query, flags) : new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), flags);
        newLine = oldLine.replace(pattern, replaceText);
      } catch {
        newLine = oldLine.replace(query, replaceText);
      }
      lines[idx] = newLine;
      const newContent = lines.join('\n');

      // Write back
      const writeRes = await fetch('/api/fs/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath, content: newContent }),
      });
      const writeData = await writeRes.json();
      if (writeData.ok) {
        updateFileContent(filePath, newContent);
        addToast(`✏️ ${filePath.split('/').pop()}:${line} 수정됨`, 'success');
        // Re-run search
        handleSearch(query);
      } else {
        throw new Error(writeData.detail || 'Write failed');
      }
    } catch (err: any) {
      addToast(`바꾸기 오류: ${err.message}`, 'error');
    } finally {
      setReplacing(false);
    }
  }, [replaceText, query, useRegex, caseSensitive, replacing, handleSearch, updateFileContent, addToast]);

  // Replace all in a single file
  const handleReplaceAllInFile = useCallback(async (filePath: string) => {
    if (!replaceText.trim() || replacing) return;
    setReplacing(true);
    try {
      const res = await fetch(`/api/fs/read?file=${encodeURIComponent(filePath)}`);
      const data = await res.json();
      if (data.content === undefined) throw new Error('Cannot read file');

      const flags = caseSensitive ? 'g' : 'gi';
      let newContent: string;
      try {
        const pattern = useRegex ? new RegExp(query, flags) : new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), flags);
        newContent = data.content.replace(pattern, replaceText);
      } catch {
        newContent = data.content.split(query).join(replaceText);
      }

      if (newContent === data.content) {
        addToast('변경사항 없음', 'info');
        setReplacing(false);
        return;
      }

      const writeRes = await fetch('/api/fs/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath, content: newContent }),
      });
      const writeData = await writeRes.json();
      if (writeData.ok) {
        updateFileContent(filePath, newContent);
        addToast(`✏️ ${filePath.split('/').pop()} 일괄 바꾸기 완료`, 'success');
        handleSearch(query);
      } else {
        throw new Error(writeData.detail || 'Write failed');
      }
    } catch (err: any) {
      addToast(`일괄 바꾸기 오류: ${err.message}`, 'error');
    } finally {
      setReplacing(false);
    }
  }, [replaceText, query, useRegex, caseSensitive, replacing, handleSearch, updateFileContent, addToast]);

  // Replace all across ALL results
  const handleReplaceAll = useCallback(async () => {
    if (!replaceText.trim() || replacing || flatMatches.length === 0) return;
    setReplacing(true);
    let success = 0;
    let fail = 0;
    const uniqueFiles = [...new Set(flatMatches.map(m => m.filePath))];
    addToast(`🔄 ${uniqueFiles.length}개 파일 일괄 바꾸기 시작...`, 'info');

    for (const filePath of uniqueFiles) {
      try {
        const res = await fetch(`/api/fs/read?file=${encodeURIComponent(filePath)}`);
        const data = await res.json();
        if (data.content === undefined) throw new Error('Cannot read file');

        const flags = caseSensitive ? 'g' : 'gi';
        let newContent: string;
        try {
          const pattern = useRegex ? new RegExp(query, flags) : new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), flags);
          newContent = data.content.replace(pattern, replaceText);
        } catch {
          newContent = data.content.split(query).join(replaceText);
        }

        if (newContent === data.content) continue;

        const writeRes = await fetch('/api/fs/write', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: filePath, content: newContent }),
        });
        const writeData = await writeRes.json();
        if (writeData.ok) {
          updateFileContent(filePath, newContent);
          success++;
        } else {
          fail++;
        }
      } catch {
        fail++;
      }
    }
    setReplacing(false);
    addToast(`✏️ ${success}개 파일 바꾸기 완료${fail > 0 ? `, ${fail}개 실패` : ''}`, fail > 0 ? 'error' : 'success');
    if (success > 0) handleSearch(query);
  }, [replaceText, query, useRegex, caseSensitive, flatMatches, replacing, handleSearch, updateFileContent, addToast]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, []);

  // Keyboard shortcut to focus replace input from search input
  const handleSearchKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Tab' && !e.shiftKey) {
      e.preventDefault();
      replaceInputRef.current?.focus();
    }
    handleKeyDown(e);
  }, [handleKeyDown]);

  if (!visible) return null;

  const showReplace = flatMatches.length > 0 || searched;

  return (
    <div className="search-panel">
      {/* ── Search Input ──────────────────────────────────── */}
      <div className="search-panel-section">
        <div className="search-input-row">
          <span className="search-icon">🔎</span>
          <input
            ref={searchInputRef}
            type="text"
            className="search-input"
            value={query}
            onChange={e => handleInputChange(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder={useRegex ? 'Search (regex)...' : 'Search files...'}
          />
          {/* Options */}
          <button
            className={`search-option-btn ${useRegex ? 'active' : ''}`}
            onClick={() => { setUseRegex(!useRegex); if (query) handleSearch(query, !useRegex, caseSensitive); }}
            title="Use Regular Expression"
          >
            .*
          </button>
          <button
            className={`search-option-btn ${caseSensitive ? 'active' : ''}`}
            onClick={() => { setCaseSensitive(!caseSensitive); if (query) handleSearch(query, useRegex, !caseSensitive); }}
            title="Case Sensitive"
          >
            Aa
          </button>
          <button className="search-close-btn" onClick={onClose} title="Close (Esc)">✕</button>
        </div>

        {/* ── Replace Input ────────────────────────────────── */}
        {showReplace && (
          <div className="search-input-row replace-row">
            <span className="search-icon">✏️</span>
            <input
              ref={replaceInputRef}
              type="text"
              className="search-input"
              value={replaceText}
              onChange={e => setReplaceText(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && replaceText.trim() && flatMatches.length > 0) {
                  e.preventDefault();
                  handleReplaceAll();
                }
                if (e.key === 'Escape') {
                  e.preventDefault();
                  setReplaceText('');
                }
                if (e.key === 'Tab' && e.shiftKey) {
                  e.preventDefault();
                  searchInputRef.current?.focus();
                }
              }}
              placeholder="Replace with..."
            />
            {flatMatches.length > 0 && replaceText.trim() && (
              <button
                className="search-replace-all-global-btn"
                onClick={handleReplaceAll}
                disabled={replacing}
                title="Replace all matches across all files"
              >
                {replacing ? '...' : `Replace All (${flatMatches.length})`}
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Results Summary ───────────────────────────────── */}
      {searched && (
        <div className="search-summary">
          {searching ? (
            <span><span className="search-spinner" /> Searching...</span>
          ) : totalFiles > 0 ? (
            <span>{totalMatches} match{totalMatches !== 1 ? 'es' : ''} in {totalFiles} file{totalFiles !== 1 ? 's' : ''}</span>
          ) : (
            <span>No results found</span>
          )}
          {flatMatches.length > 0 && focusedIdx >= 0 && (
            <span className="search-navigation">
              {focusedIdx + 1}/{flatMatches.length}
              <button className="search-nav-btn" onClick={() => setFocusedIdx(prev => Math.max(prev - 1, 0))} disabled={focusedIdx <= 0}>▲</button>
              <button className="search-nav-btn" onClick={() => setFocusedIdx(prev => Math.min(prev + 1, flatMatches.length - 1))} disabled={focusedIdx >= flatMatches.length - 1}>▼</button>
            </span>
          )}
        </div>
      )}

      {/* ── Results List ──────────────────────────────────── */}
      <div className="search-results-list" ref={resultsRef}>
        {searching ? (
          <div className="search-status"><span className="search-spinner" /> Searching...</div>
        ) : results.length > 0 ? (
          results.map((result, i) => (
            <FileResult
              key={`${result.file_path}-${i}`}
              result={result}
              query={query}
              useRegex={useRegex}
              replaceText={replaceText}
              onOpenMatch={handleOpenMatch}
              onReplaceSingle={handleReplaceSingle}
              onReplaceAllInFile={handleReplaceAllInFile}
              isFocused={false}
              focusedMatchKey={focusedIdx >= 0 ? flatMatches[focusedIdx]?.filePath + ':' + flatMatches[focusedIdx]?.line : null}
            />
          ))
        ) : searched ? (
          <div className="search-empty">
            <div className="search-empty-icon">🔍</div>
            <div>No files found matching "{query}"</div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default SearchPanel;
