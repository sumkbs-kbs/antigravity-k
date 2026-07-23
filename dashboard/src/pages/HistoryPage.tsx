/**
 * HistoryPage — Local File History Timeline
 * ===========================================
 * Full-page interface for browsing file snapshots, comparing versions,
 * and visualizing change history over time.
 *
 * Layout:
 *   [File List (left)]  [Timeline (center)]  [Diff Viewer (right)]
 */

import React, { useCallback, useMemo, useState } from 'react';
import { useLocalHistoryStore } from '../stores/localHistoryStore';
import { useEditorStore } from '../stores/editorStore';
import LocalHistoryTimeline from '../components/History/LocalHistoryTimeline';
import SnapshotDiffView from '../components/History/SnapshotDiffView';
import { useUiStore } from '../stores/uiStore';

/* ─── File selector sidebar ────────────────────────────────── */

const FileListSidebar: React.FC = () => {
  const {
    getAllFiles, selectedFile, setSelectedFile,
    clearFileHistory, clearAllHistory, snapshots,
  } = useLocalHistoryStore();

  const { addToast } = useUiStore();
  const files = useMemo(() => getAllFiles(), [getAllFiles]);

  const totalSnapshots = useMemo(
    () => Object.values(snapshots).reduce((sum, arr) => sum + arr.length, 0),
    [snapshots],
  );

  const handleClearFile = useCallback((e: React.MouseEvent, filePath: string) => {
    e.stopPropagation();
    clearFileHistory(filePath);
    addToast(`🗑️ ${filePath} 히스토리 삭제됨`, 'info');
  }, [clearFileHistory, addToast]);

  const handleClearAll = useCallback(() => {
    if (files.length === 0) return;
    if (confirm('모든 파일의 로컬 히스토리를 삭제하시겠습니까?')) {
      clearAllHistory();
      addToast('🗑️ 전체 히스토리 삭제됨', 'info');
    }
  }, [files.length, clearAllHistory, addToast]);

  return (
    <div className="history-file-list">
      <div className="history-file-list-header">
        <span className="history-file-list-title">📁 Files</span>
        <div className="history-file-list-actions">
          <span className="history-file-count">{totalSnapshots} snapshots</span>
          {files.length > 0 && (
            <button
              className="history-header-btn"
              onClick={handleClearAll}
              title="Clear all history"
              aria-label="전체 히스토리 삭제"
            >
              🗑️
            </button>
          )}
        </div>
      </div>
      <div className="history-file-scroll">
        {files.length === 0 ? (
          <div className="history-file-empty">
            <span className="history-file-empty-icon">📜</span>
            <span>저장된 히스토리가 없습니다</span>
            <span className="history-file-empty-hint">파일을 편집하면 자동으로 스냅샷이 저장됩니다</span>
          </div>
        ) : (
          files.map(file => (
            <div
              key={file.filePath}
              className={`history-file-item ${file.filePath === selectedFile ? 'active' : ''}`}
              onClick={() => setSelectedFile(file.filePath)}
              role="button"
              tabIndex={0}
            >
              <div className="history-file-icon">📄</div>
              <div className="history-file-info">
                <span className="history-file-name">{file.fileName}</span>
                <span className="history-file-path">{file.filePath}</span>
              </div>
              <div className="history-file-count-badge">{file.count}</div>
              <button
                className="history-file-remove"
                onClick={e => handleClearFile(e, file.filePath)}
                title="Delete history for this file"
                aria-label={`${file.fileName} 히스토리 삭제`}
              >
                ✕
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

/* ─── History Settings Bar ─────────────────────────────────── */  const HistorySettingsBar: React.FC = () => {
  const {
    autoSaveEnabled, maxSnapshotsPerFile, selectedFile,
    setAutoSaveEnabled, setMaxSnapshotsPerFile, addSnapshot,
  } = useLocalHistoryStore();
  const { addToast } = useUiStore();
  const { openFiles } = useEditorStore();
  const [editingMax, setEditingMax] = useState(false);
  const [maxInput, setMaxInput] = useState(String(maxSnapshotsPerFile));

  const handleSaveNow = useCallback(() => {
    if (!selectedFile) {
      addToast('왼쪽에서 파일을 선택하세요', 'info');
      return;
    }
    const file = openFiles.find(f => f.path === selectedFile);
    if (!file) {
      addToast('선택한 파일이 열려 있지 않습니다', 'info');
      return;
    }
    addSnapshot({
      filePath: file.path,
      fileName: file.name,
      content: file.content,
      source: 'manual',
      label: '수동 저장',
    }, true);  // force=true bypasses autoSaveEnabled check
    addToast(`💾 ${file.name} 스냅샷 저장됨`, 'success');
  }, [selectedFile, openFiles, addSnapshot, addToast]);

  const handleMaxChange = useCallback(() => {
    const val = parseInt(maxInput);
    if (isNaN(val) || val < 5) {
      setMaxInput(String(maxSnapshotsPerFile));
      addToast('최소 5개 이상 입력하세요', 'info');
    } else {
      setMaxSnapshotsPerFile(val);
      addToast(`파일당 최대 ${val}개 스냅샷으로 설정됨`, 'success');
    }
    setEditingMax(false);
  }, [maxInput, maxSnapshotsPerFile, setMaxSnapshotsPerFile, addToast]);

  return (
    <div className="history-settings-bar">
      {/* Auto-save toggle */}
      <label className="history-toggle-label">
        <input
          type="checkbox"
          checked={autoSaveEnabled}
          onChange={e => setAutoSaveEnabled(e.target.checked)}
        />
        <span className="toggle-track-sm" />
        <span>자동 저장</span>
      </label>

      {/* Max snapshots per file */}
      <div className="history-max-setting">
        <span className="history-max-label">최대</span>
        {editingMax ? (
          <input
            type="number"
            className="history-max-input"
            value={maxInput}
            min={5}
            max={200}
            onChange={e => setMaxInput(e.target.value)}
            onBlur={handleMaxChange}
            onKeyDown={e => e.key === 'Enter' && handleMaxChange()}
            autoFocus
          />
        ) : (
          <span
            className="history-max-value"
            onClick={() => { setMaxInput(String(maxSnapshotsPerFile)); setEditingMax(true); }}
            title="클릭하여 변경"
          >
            {maxSnapshotsPerFile}
          </span>
        )}
        <span className="history-max-label">/파일</span>
      </div>

      {/* Save now button */}
      <button className="history-save-now-btn" onClick={handleSaveNow} title="현재 파일 상태를 스냅샷으로 저장">
        💾 지금 저장
      </button>
    </div>
  );
};

/* ─── Main History Page ────────────────────────────────────── */

const HistoryPage: React.FC = () => {
  const { selectedFile, compareIds } = useLocalHistoryStore();

  return (
    <div className="page-container full-height-page history-page">
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2>📜 로컬 히스토리 <span>Local History</span></h2>
            <p className="page-subtitle">
              파일 변경 내역을 시간순으로 확인하고, 두 시점을 비교하여 차이를 검토합니다.
            </p>
          </div>
          <div className="history-header-actions">
            <HistorySettingsBar />
            {compareIds[0] && compareIds[1] && (
              <span className="history-compare-badge">
                🔍 A↔B 비교 중
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="history-layout">
        {/* Left: File List */}
        <div className="history-left-panel">
          <FileListSidebar />
        </div>

        {/* Center: Timeline */}
        <div className="history-center-panel">
          {selectedFile ? (
            <LocalHistoryTimeline />
          ) : (
            <div className="timeline-select-file-hint">
              <span className="timeline-empty-icon">📂</span>
              <span>왼쪽에서 파일을 선택하세요</span>
            </div>
          )}
        </div>

        {/* Right: Diff Viewer */}
        <div className="history-right-panel">
          <SnapshotDiffView />
        </div>
      </div>
    </div>
  );
};

export default HistoryPage;
