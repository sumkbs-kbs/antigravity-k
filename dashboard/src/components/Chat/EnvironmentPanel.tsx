/**
 * EnvironmentPanel — Antigravity-style right-hand "환경" rail
 * ===========================================================
 * Mirrors the Google Antigravity Agent Manager right panel:
 *  - 환경: 변경 사항 (+/− diff stats), 로그 (expandable commits),
 *          git branch selector, 커밋 또는 푸시, 풀 리퀘스트 만들기
 *  - 파일 액티브티: recently touched files (git status)
 *  - 소스: MCP servers
 * The legacy inspector editor/changes live in the 코드 / 변경 tabs so
 * the existing editor functionality stays reachable from the same rail.
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchGitStatus, fetchGitBranches, fetchGitLog } from '../../stores/gitApi';
import type { GitBranch, GitCommit, GitFile } from '../../stores/gitSchema';
import { useChangeStore } from '../../stores/changeStore';
import { useUiStore } from '../../stores/uiStore';

export type EnvPanelTab = 'env' | 'code' | 'changes';

interface Props {
  open: boolean;
  tab: EnvPanelTab;
  onTabChange: (tab: EnvPanelTab) => void;
  onClose: () => void;
  branch: string;
  editorContent: React.ReactNode;
  changesContent: React.ReactNode;
}

function workspacePath(): string {
  return localStorage.getItem('agk_active_project') || '/';
}

function shortFilePath(filePath: string): string {
  const parts = filePath.split(/[/\\]/);
  return parts.slice(-2).join('/');
}

export const EnvironmentPanel: React.FC<Props> = ({
  open,
  tab,
  onTabChange,
  onClose,
  branch,
  editorContent,
  changesContent,
}) => {
  const navigate = useNavigate();
  const { addToast } = useUiStore();
  const changes = useChangeStore((s) => s.changes);

  const [logOpen, setLogOpen] = useState<boolean>(false);
  const [branchOpen, setBranchOpen] = useState<boolean>(false);
  const [gitFiles, setGitFiles] = useState<GitFile[]>([]);
  const [branches, setBranches] = useState<GitBranch[]>([]);
  const [commits, setCommits] = useState<GitCommit[]>([]);

  const diffAdds = changes.reduce((sum, c) => sum + (c.diffStats?.additions ?? 0), 0);
  const diffDels = changes.reduce((sum, c) => sum + (c.diffStats?.deletions ?? 0), 0);

  useEffect(() => {
    if (!open) return;
    const path = workspacePath();
    fetchGitStatus(path)
      .then((res) => { if (res.ok) setGitFiles(res.files); })
      .catch(() => {});
    fetchGitBranches(path)
      .then((res) => { if (res.ok) setBranches(res.branches); })
      .catch(() => {});
    fetchGitLog(path, 5, branch)
      .then((res) => { if (res.ok) setCommits(res.commits); })
      .catch(() => {});
  }, [open, branch]);

  if (!open) return null;

  const goGit = (note: string) => {
    addToast(note, 'info');
    navigate('/git');
  };

  return (
    <aside className="agk-env-panel" aria-label="환경 패널">
      {/* ── Tab bar: 환경 / 코드 / 변경 ─────────────────────── */}
      <div className="env-tab-bar">
        <button
          type="button"
          className={`env-tab ${tab === 'env' ? 'active' : ''}`}
          onClick={() => onTabChange('env')}
        >
          환경
        </button>
        <button
          type="button"
          className={`env-tab ${tab === 'code' ? 'active' : ''}`}
          onClick={() => onTabChange('code')}
        >
          코드
        </button>
        <button
          type="button"
          className={`env-tab ${tab === 'changes' ? 'active' : ''}`}
          onClick={() => onTabChange('changes')}
        >
          변경 {changes.length > 0 && <span className="env-tab-count">{changes.length}</span>}
        </button>
        <div className="env-tab-spacer" />
        <button type="button" className="env-close-btn" onClick={onClose} aria-label="환경 패널 닫기">
          ✕
        </button>
      </div>

      {tab === 'env' && (
        <div className="env-scroll-area">
          {/* ── 환경 section ─────────────────────────────────── */}
          <div className="env-section">
            <div className="env-section-header">
              <span className="env-section-title">환경</span>
              <button
                type="button"
                className="env-plus-btn"
                aria-label="환경 추가"
                title="새 환경 추가"
                onClick={() => addToast('새 환경 구성은 설정 페이지에서 추가할 수 있습니다.', 'info')}
              >
                ⊕
              </button>
            </div>

            {/* 변경 사항 row */}
            <button type="button" className="env-row" onClick={() => onTabChange('changes')}>
              <span className="env-row-icon">⊟</span>
              <span className="env-row-label">변경 사항</span>
              <span className="env-row-stat">
                {diffAdds > 0 && <span className="stat-add">+{diffAdds.toLocaleString()}</span>}
                {diffDels > 0 && <span className="stat-del">−{diffDels.toLocaleString()}</span>}
                {diffAdds === 0 && diffDels === 0 && (
                  <span className="env-row-muted">
                    {gitFiles.length > 0 ? `${gitFiles.length}개 파일` : '변경 없음'}
                  </span>
                )}
              </span>
            </button>

            {/* 로그 row (expandable) */}
            <div className="env-row-group">
              <button
                type="button"
                className="env-row"
                onClick={() => setLogOpen((v) => !v)}
                aria-expanded={logOpen}
              >
                <span className="env-row-icon">▤</span>
                <span className="env-row-label">로그</span>
                <span className={`env-chevron ${logOpen ? 'open' : ''}`}>⌄</span>
              </button>
              {logOpen && (
                <div className="env-sub-list">
                  {commits.length === 0 ? (
                    <div className="env-sub-empty">커밋 로그를 불러올 수 없습니다.</div>
                  ) : (
                    commits.map((c) => (
                      <div key={c.hash} className="env-log-row" title={c.message}>
                        <span className="env-log-hash">{c.short_hash}</span>
                        <span className="env-log-msg">{c.message}</span>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Branch row (expandable list) */}
            <div className="env-row-group">
              <button
                type="button"
                className="env-row"
                onClick={() => setBranchOpen((v) => !v)}
                aria-expanded={branchOpen}
              >
                <span className="env-row-icon">⑂</span>
                <span className="env-row-label branch-name">{branch}</span>
                <span className={`env-chevron ${branchOpen ? 'open' : ''}`}>⌄</span>
              </button>
              {branchOpen && (
                <div className="env-sub-list">
                  {branches.length === 0 ? (
                    <div className="env-sub-empty">브랜치 목록을 불러올 수 없습니다.</div>
                  ) : (
                    branches.slice(0, 8).map((b) => (
                      <button
                        key={b.name}
                        type="button"
                        className={`env-branch-row ${b.is_current ? 'current' : ''}`}
                        onClick={() => goGit('브랜치 전환은 Git 페이지에서 수행합니다.')}
                      >
                        <span className="env-branch-name">{b.name}</span>
                        {b.is_current && <span className="env-branch-current">현재</span>}
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Action rows */}
            <button type="button" className="env-row" onClick={() => goGit('커밋·푸시는 Git 페이지에서 진행합니다.')}>
              <span className="env-row-icon">⟳</span>
              <span className="env-row-label">커밋 또는 푸시</span>
            </button>
            <button type="button" className="env-row" onClick={() => goGit('풀 리퀘스트는 Git 페이지에서 만들 수 있습니다.')}>
              <span className="env-row-icon">⑆</span>
              <span className="env-row-label">풀 리퀘스트 만들기</span>
            </button>
          </div>

          <div className="env-divider" />

          {/* ── 파일 액티브티 section ─────────────────────────── */}
          <div className="env-section">
            <div className="env-section-header">
              <span className="env-section-title">파일 액티브티</span>
            </div>
            {gitFiles.length === 0 && changes.length === 0 ? (
              <div className="env-sub-empty">최근 파일 활동이 없습니다.</div>
            ) : (
              <>
                {changes.slice(0, 8).map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className="env-file-row"
                    onClick={() => onTabChange('changes')}
                    title={c.filePath}
                  >
                    <span className="env-file-name">{c.fileName}</span>
                    <span className="env-file-stat">
                      <span className="stat-add">+{c.diffStats?.additions ?? 0}</span>
                      <span className="stat-del">−{c.diffStats?.deletions ?? 0}</span>
                    </span>
                  </button>
                ))}
                {gitFiles.slice(0, 8).map((f) => (
                  <button
                    key={`${f.file_path}-${f.x}${f.y}`}
                    type="button"
                    className="env-file-row"
                    onClick={() => goGit('파일 상태는 Git 페이지 Changes 탭에서 확인합니다.')}
                    title={f.file_path}
                  >
                    <span className="env-file-name">{shortFilePath(f.file_path)}</span>
                    <span className="env-file-status-letter">
                      {(f.staged_status && f.staged_status !== ' ') ? f.staged_status : f.unstaged_status}
                    </span>
                  </button>
                ))}
                <div className="env-file-footer">
                  파일 {gitFiles.length + changes.length}개
                </div>
              </>
            )}
          </div>

          <div className="env-divider" />

          {/* ── 소스 (MCP) section ────────────────────────────── */}
          <div className="env-section">
            <div className="env-section-header">
              <span className="env-section-title">소스</span>
              <button
                type="button"
                className="env-plus-btn"
                aria-label="소스 추가"
                title="MCP 서버 추가"
                onClick={() => {
                  addToast('MCP 서버 관리는 스킬 페이지 MCP 탭에서 진행합니다.', 'info');
                  navigate('/skills');
                }}
              >
                ⊕
              </button>
            </div>
            <div className="env-mcp-row">
              <span className="env-mcp-icon">⊞</span>
              <div className="env-mcp-text">
                <span className="env-mcp-name">codebase-memory-mcp</span>
                <span className="env-mcp-status">연결됨</span>
              </div>
            </div>
            <button
              type="button"
              className="env-mcp-more"
              onClick={() => {
                addToast('전체 MCP 서버 목록을 엽니다.', 'info');
                navigate('/skills');
              }}
            >
              모두 보기
            </button>
          </div>
        </div>
      )}

      {tab === 'code' && (
        <div className="env-content-area">
          {editorContent}
        </div>
      )}

      {tab === 'changes' && (
        <div className="env-content-area">
          {changesContent}
        </div>
      )}
    </aside>
  );
};

export default EnvironmentPanel;
