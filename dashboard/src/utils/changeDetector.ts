/**
 * changeDetector — AI 응답에서 파일 변경 사항을 자동 감지
 * ==========================================================
 * 
 * 감지 패턴:
 * 1. 코드 블록 with 파일 경로 주석: ```python:path/to/file.py
 * 2. Diff 형식: --- a/file +++ b/file 블록
 * 3. 명시적 마커: [FILE: path/to/file.py]
 * 4. WebSocket FileModified 이벤트 (외부 통합)
 * 
 * 감지된 변경 사항을 Change Store에 자동 등록합니다.
 */

import { useChangeStore } from '../stores/changeStore';

/* ─── Types ───────────────────────────────────────────────── */

export interface PendingFileRead {
  filePath: string;
  fileName: string;
  newContent: string;
  description?: string;
}

/* ─── Constants ───────────────────────────────────────────── */

const MAX_CHANGE_SIZE = 100 * 1024; // 100KB per change max

/* ─── Pattern: ```lang:path 코드 블록 ────────────────────────── */

const CODE_BLOCK_WITH_PATH = /```(\w+):([^\n`]+)\n?([\s\S]*?)```/g;

/* ─── Pattern: [FILE: path] 마커 ───────────────────────────── */

const FILE_MARKER = /\[FILE:\s*([^\]]+)\]\n?([\s\S]*?)(?=\n\[FILE:|```|$)/g;

/* ─── Read file content from backend ───────────────────────── */

async function fetchFileContent(filePath: string): Promise<string | null> {
  try {
    const res = await fetch(`/api/fs/read?file=${encodeURIComponent(filePath)}`);
    const data = await res.json();
    if (data.content !== undefined) {
      return data.content;
    }
    return null; // File doesn't exist (new file)
  } catch {
    return null;
  }
}

/* ─── Extract file name from path ──────────────────────────── */

function getFileName(filePath: string): string {
  return filePath.split('/').pop() || filePath.split('\\').pop() || filePath;
}

/* ─── Clean content ────────────────────────────────────────── */

function cleanContent(content: string): string {
  return content
    .trim()
    .replace(/^[\n\r]+/, '')
    .replace(/[\n\r]+$/, '');
}

/* ─── Check if change already exists in the store (dedup) ──── */

function isDuplicateChange(filePath: string, newContent: string): boolean {
  const { changes } = useChangeStore.getState();
  return changes.some(c => c.filePath === filePath && c.newContent.trim() === newContent.trim());
}

/* ─── Register change in Change Store ───────────────────────── */

function registerChange(filePath: string, originalContent: string, newContent: string, description?: string) {
  if (!filePath || !newContent) return;
  if (newContent.length > MAX_CHANGE_SIZE) return;
  if (isDuplicateChange(filePath, newContent)) return;

  const fileName = getFileName(filePath);
  useChangeStore.getState().addChange({
    filePath,
    fileName,
    originalContent: originalContent || '',
    newContent: cleanContent(newContent),
    description: description || `AI 제안: ${fileName}`,
  });
}

/* ─── Parse code blocks with file path annotations ──────────── */

function parseCodeBlocks(content: string, pendingReads: PendingFileRead[], codeBlockPaths: Set<string>): void {
  CODE_BLOCK_WITH_PATH.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = CODE_BLOCK_WITH_PATH.exec(content)) !== null) {
    const rawPath = match[2].trim();
    const codeContent = match[3];
    if (rawPath && codeContent && !codeBlockPaths.has(rawPath)) {
      codeBlockPaths.add(rawPath);
      pendingReads.push({
        filePath: rawPath,
        fileName: getFileName(rawPath),
        newContent: codeContent,
        description: `AI 제안: ${getFileName(rawPath)}`,
      });
    }
  }
}

/* ─── Parse [FILE: path] markers ───────────────────────────── */

function parseFileMarkers(content: string, pendingReads: PendingFileRead[], skipPaths: Set<string>): void {
  FILE_MARKER.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = FILE_MARKER.exec(content)) !== null) {
    const rawPath = match[1].trim();
    const fileContent = match[2].trim();
    if (rawPath && fileContent && !skipPaths.has(rawPath)) {
      pendingReads.push({
        filePath: rawPath,
        fileName: getFileName(rawPath),
        newContent: fileContent,
        description: `파일 생성/수정: ${getFileName(rawPath)}`,
      });
    }
  }
}

/* ─── Main detection logic ─────────────────────────────────── */

/**
 * Parse full assistant content for file change patterns
 * and register them in the Change Store.
 * Returns the number of changes detected.
 */
export async function detectChangesFromContent(content: string): Promise<number> {
  if (!content || content.length < 20) return 0;

  let detectedCount = 0;
  const pendingReads: PendingFileRead[] = [];
  const codeBlockPaths = new Set<string>();

  // ── Pattern 1: ```lang:path 코드 블록 ──────────────────────
  parseCodeBlocks(content, pendingReads, codeBlockPaths);

  // ── Pattern 2: [FILE: path] 마커 ────────────────────────────
  parseFileMarkers(content, pendingReads, codeBlockPaths);

  // ── Return early if nothing found ─────────────────────────
  if (pendingReads.length === 0) return 0;

  // ── Read original content for all files in parallel ────────
  const readPromises = pendingReads.map(async (pending) => {
    const originalContent = await fetchFileContent(pending.filePath);
    return { pending, originalContent };
  });

  const results = await Promise.all(readPromises);

  for (const { pending, originalContent } of results) {
    // Only register if content actually changed (file exists with different content, or is new)
    if (originalContent === null || cleanContent(originalContent) !== cleanContent(pending.newContent)) {
      registerChange(
        pending.filePath,
        originalContent || '',
        pending.newContent,
        pending.description,
      );
      detectedCount++;
    }
  }

  return detectedCount;
}

/**
 * Detect file changes from the full assistant response
 * after streaming completes. Returns the count of changes detected.
 */
export async function detectChangesFromAssistantContent(content: string): Promise<number> {
  return detectChangesFromContent(content);
}

/**
 * Register a file modification from WebSocket event.
 * Reads the current file content and adds to Change Store.
 */
export async function registerFileModification(filePath: string, fileName: string): Promise<boolean> {
  try {
    const originalContent = await fetchFileContent(filePath);
    if (originalContent === null) return false;

    // Read previous version (before modification) from git HEAD
    let previousContent: string | null = null;
    try {
      const gitRes = await fetch(`/api/git/file-content?path=.&file=${encodeURIComponent(filePath)}&ref=HEAD`);
      const gitData = await gitRes.json();
      if (gitData.ok && gitData.content !== undefined) {
        previousContent = gitData.content;
      }
    } catch {
      // Git not available — register as a new change from scratch
    }

    if (previousContent !== null && cleanContent(previousContent) === cleanContent(originalContent)) {
      return false; // No actual change
    }

    registerChange(
      filePath,
      previousContent || '',
      originalContent,
      `파일 수정: ${fileName}`,
    );

    return true;
  } catch {
    return false;
  }
}
