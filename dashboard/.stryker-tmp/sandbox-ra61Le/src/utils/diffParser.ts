/**
 * diffParser — Unified diff format parser
 * =========================================
 * Parses `--- a/+++ b/` unified diff output into structured
 * line objects with type, content, and line numbers.
 *
 * Supports:
 * - diff --git headers
 * - @@ hunk headers with old/new line numbers
 * - Added (+), removed (-), and context ( ) lines
 * - new file / deleted file markers
 * - Binary diff markers
 */
// @ts-nocheck


export interface DiffLine {
  type: 'header' | 'added' | 'removed' | 'context' | 'hunk';
  content: string;
  oldLine?: number;
  newLine?: number;
}

export interface ParsedDiff {
  lines: DiffLine[];
  /** The original file path from --- a/ */
  oldPath?: string;
  /** The new file path from +++ b/ */
  newPath?: string;
  /** Whether this is a full unified diff or partial */
  isUnifiedDiff: boolean;
}

/**
 * Check if a string is in unified diff format.
 * Looks for typical diff markers.
 */
export function isUnifiedDiff(text: string): boolean {
  if (!text) return false;
  const firstLine = text.split('\n')[0];
  return (
    firstLine.startsWith('diff --git') ||
    firstLine.startsWith('--- ') ||
    text.startsWith('@@') ||
    text.includes('\n--- ') ||
    text.includes('\n@@ ')
  );
}

/**
 * Parse a unified diff string into structured DiffLine objects.
 */
export function parseDiff(diff: string): DiffLine[] {
  const lines: DiffLine[] = [];
  for (const rawLine of diff.split('\n')) {
    if (
      rawLine.startsWith('diff --git') ||
      rawLine.startsWith('index ') ||
      rawLine.startsWith('new file') ||
      rawLine.startsWith('deleted file') ||
      rawLine.startsWith('old mode') ||
      rawLine.startsWith('new mode') ||
      rawLine.startsWith('similarity index') ||
      rawLine.startsWith('rename from') ||
      rawLine.startsWith('rename to') ||
      rawLine.startsWith('copy from') ||
      rawLine.startsWith('copy to') ||
      rawLine.startsWith('Binary files')
    ) {
      lines.push({ type: 'header', content: rawLine });
    } else if (rawLine.startsWith('--- ')) {
      lines.push({ type: 'header', content: rawLine });
    } else if (rawLine.startsWith('+++ ')) {
      lines.push({ type: 'header', content: rawLine });
    } else if (rawLine.startsWith('@@')) {
      // Parse hunk header: @@ -oldStart,oldCount +newStart,newCount @@
      const match = rawLine.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      lines.push({
        type: 'hunk',
        content: rawLine,
        oldLine: match ? parseInt(match[1]) : undefined,
        newLine: match ? parseInt(match[2]) : undefined,
      });
    } else if (rawLine.startsWith('+')) {
      lines.push({ type: 'added', content: rawLine.substring(1) });
    } else if (rawLine.startsWith('-')) {
      lines.push({ type: 'removed', content: rawLine.substring(1) });
    } else if (rawLine.startsWith(' ')) {
      lines.push({ type: 'context', content: rawLine.substring(1) });
    } else if (rawLine.startsWith('\\')) {
      // No newline at end of file marker
      lines.push({ type: 'header', content: rawLine });
    } else if (rawLine.trim() === '') {
      // Skip empty lines between diff sections
      continue;
    } else {
      lines.push({ type: 'context', content: rawLine });
    }
  }
  return lines;
}

/**
 * Parse full diff including extracting file paths from headers.
 */
export function parseDiffFull(diff: string): ParsedDiff {
  const lines = parseDiff(diff);
  let oldPath: string | undefined;
  let newPath: string | undefined;

  for (const line of lines) {
    if (line.type === 'header') {
      if (line.content.startsWith('--- a/')) {
        oldPath = line.content.slice(6);
      } else if (line.content.startsWith('+++ b/')) {
        newPath = line.content.slice(6);
      }
    }
  }

  return {
    lines,
    oldPath,
    newPath,
    isUnifiedDiff: isUnifiedDiff(diff),
  };
}

/**
 * Compute the resulting content by applying a unified diff to the original text.
 * Returns the applied content, or the original text if parsing fails.
 */
export function applyUnifiedDiff(original: string, diff: string): string {
  const parsedLines = parseDiff(diff);
  const originalLines = original.split('\n');
  const result: string[] = [];

  let oldLine = 0;
  let newLine = 0;
  let inHunk = false;

  for (const line of parsedLines) {
    if (line.type === 'hunk') {
      inHunk = true;
      oldLine = line.oldLine || 1;
      // Copy original lines up to the hunk start
      while (result.length < oldLine - 1) {
        result.push(originalLines[result.length] || '');
      }
    } else if (inHunk && line.type === 'context') {
      // Context line: keep original
      result.push(originalLines[oldLine - 1] ?? '');
      oldLine++;
      newLine++;
    } else if (inHunk && line.type === 'removed') {
      // Removed line: skip original
      oldLine++;
    } else if (inHunk && line.type === 'added') {
      // Added line: insert new content
      result.push(line.content);
      newLine++;
    } else if (line.type === 'header') {
      inHunk = false;
    }
  }

  // Copy remaining original lines
  while (result.length < originalLines.length) {
    result.push(originalLines[result.length]);
  }

  return result.join('\n');
}
