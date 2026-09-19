import * as http from 'node:http';
import * as vscode from 'vscode';

const DEFAULT_PORT = 54321;
const DEFAULT_DEBOUNCE_MILLISECONDS = 100;
const DEFAULT_REQUEST_TIMEOUT_MILLISECONDS = 1000;

type WireSyncState = {
  readonly active_file: string;
  readonly cursor_line: number;
  readonly open_files: readonly string[];
};

type SyncConfiguration = {
  readonly port: number;
  readonly debounceMilliseconds: number;
  readonly requestTimeoutMilliseconds: number;
};

export type IdeSyncStatus = {
  readonly lastState: WireSyncState | null;
  readonly lastError: string | null;
};

export type IdeSyncApi = {
  readonly status: IdeSyncStatus;
  sendNow(): void;
  stop(): void;
};

let api: IdeSyncApi | undefined;
let outputChannel: vscode.OutputChannel | undefined;
let sendTimer: NodeJS.Timeout | undefined;
let activeRequest: http.ClientRequest | undefined;
let lastState: WireSyncState | null = null;
let lastError: string | null = null;
let disposed = false;
let stopping = false;

function configuration(): SyncConfiguration {
  const values = vscode.workspace.getConfiguration('antigravityK.ideSync');
  const port = values.get<number>('port', DEFAULT_PORT);
  const debounceMilliseconds = values.get<number>(
    'debounceMilliseconds',
    DEFAULT_DEBOUNCE_MILLISECONDS,
  );
  const requestTimeoutMilliseconds = values.get<number>(
    'requestTimeoutMilliseconds',
    DEFAULT_REQUEST_TIMEOUT_MILLISECONDS,
  );

  return {
    port: Number.isInteger(port) && port >= 1 && port <= 65535 ? port : DEFAULT_PORT,
    debounceMilliseconds:
      Number.isFinite(debounceMilliseconds) && debounceMilliseconds >= 0
        ? Math.min(debounceMilliseconds, 5000)
        : DEFAULT_DEBOUNCE_MILLISECONDS,
    requestTimeoutMilliseconds:
      Number.isFinite(requestTimeoutMilliseconds) && requestTimeoutMilliseconds >= 100
        ? Math.min(requestTimeoutMilliseconds, 30000)
        : DEFAULT_REQUEST_TIMEOUT_MILLISECONDS,
  };
}

function filePath(document: vscode.TextDocument): string | null {
  return document.uri.scheme === 'file' ? document.uri.fsPath : null;
}

function currentState(): WireSyncState | null {
  const editor = vscode.window.activeTextEditor;
  if (editor === undefined) {
    return null;
  }

  const activeFile = filePath(editor.document);
  if (activeFile === null) {
    return null;
  }

  const openFiles = new Set<string>();
  for (const document of vscode.workspace.textDocuments) {
    const path = filePath(document);
    if (path !== null) {
      openFiles.add(path);
    }
  }

  return {
    active_file: activeFile,
    cursor_line: editor.selection.active.line + 1,
    open_files: [...openFiles].sort(),
  };
}

function status(): IdeSyncStatus {
  return {
    lastState:
      lastState === null
        ? null
        : {
            active_file: lastState.active_file,
            cursor_line: lastState.cursor_line,
            open_files: [...lastState.open_files],
          },
    lastError,
  };
}

function recordError(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  lastError = message;
  outputChannel?.appendLine(`IDE sync failed: ${message}`);
}

function sendState(): void {
  if (disposed || stopping) {
    return;
  }

  const state = currentState();
  lastState = state;
  if (state === null) {
    lastError = null;
    outputChannel?.appendLine('IDE sync skipped: no active file editor');
    return;
  }

  const settings = configuration();
  const payload = JSON.stringify(state);
  lastError = null;
  outputChannel?.appendLine(
    `Syncing ${state.active_file}:${state.cursor_line} to 127.0.0.1:${settings.port}`,
  );

  activeRequest?.destroy();
  const request = http.request(
    {
      hostname: '127.0.0.1',
      port: settings.port,
      path: '/update',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
    },
    (response) => {
      response.on('data', () => undefined);
      response.on('end', () => {
        if (activeRequest !== request) {
          return;
        }
        activeRequest = undefined;
        if (response.statusCode === undefined || response.statusCode < 200 || response.statusCode >= 300) {
          recordError(new Error(`Ssak-Ai returned HTTP ${response.statusCode ?? 'unknown'}`));
          return;
        }
        lastError = null;
        outputChannel?.appendLine(`IDE sync accepted (HTTP ${response.statusCode})`);
      });
    },
  );

  activeRequest = request;
  request.setTimeout(settings.requestTimeoutMilliseconds, () => {
    request.destroy(new Error(`IDE sync timed out after ${settings.requestTimeoutMilliseconds}ms`));
  });
  request.on('error', (error: NodeJS.ErrnoException) => {
    if (activeRequest !== request) {
      return;
    }
    activeRequest = undefined;
    recordError(error);
  });
  request.end(payload);
}

function scheduleSend(): void {
  if (disposed) {
    return;
  }

  const delay = configuration().debounceMilliseconds;
  if (sendTimer !== undefined) {
    clearTimeout(sendTimer);
  }
  if (delay === 0) {
    sendTimer = undefined;
    sendState();
    return;
  }
  sendTimer = setTimeout(() => {
    sendTimer = undefined;
    sendState();
  }, delay);
}

function messageForStatus(value: IdeSyncStatus): string {
  if (value.lastState === null) {
    return 'Ssak-Ai IDE Sync: no active file editor';
  }
  if (value.lastError !== null) {
    return `Ssak-Ai IDE Sync: last error — ${value.lastError}`;
  }
  return `Ssak-Ai IDE Sync: ${value.lastState.active_file}:${value.lastState.cursor_line}`;
}

export function activate(context: vscode.ExtensionContext): IdeSyncApi {
  if (api !== undefined) {
    return api;
  }

  disposed = false;
  stopping = false;
  outputChannel = vscode.window.createOutputChannel('Ssak-Ai IDE Sync');
  const command = vscode.commands.registerCommand(
    'antigravity-k-sync.showStatus',
    (): IdeSyncStatus => {
      const current = status();
      void vscode.window.showInformationMessage(messageForStatus(current));
      return current;
    },
  );
  const activeEditorChange = vscode.window.onDidChangeActiveTextEditor(scheduleSend);
  const selectionChange = vscode.window.onDidChangeTextEditorSelection(
    (event: vscode.TextEditorSelectionChangeEvent) => {
      if (event.textEditor === vscode.window.activeTextEditor) {
        scheduleSend();
      }
    },
  );
  const documentChange = vscode.workspace.onDidChangeTextDocument(scheduleSend);
  const configurationChange = vscode.workspace.onDidChangeConfiguration(
    (event: vscode.ConfigurationChangeEvent) => {
      if (event.affectsConfiguration('antigravityK.ideSync')) {
        scheduleSend();
      }
    },
  );

  context.subscriptions.push(
    outputChannel,
    command,
    activeEditorChange,
    selectionChange,
    documentChange,
    configurationChange,
  );

  api = {
    get status() {
      return status();
    },
    sendNow() {
      sendState();
    },
    stop() {
      stop();
    },
  };
  scheduleSend();
  return api;
}

function stop(): void {
  stopping = true;
  disposed = true;
  if (sendTimer !== undefined) {
    clearTimeout(sendTimer);
    sendTimer = undefined;
  }
  activeRequest?.destroy();
  activeRequest = undefined;
  api = undefined;
  const channel = outputChannel;
  outputChannel = undefined;
  channel?.appendLine('Ssak-Ai IDE Sync stopped');
}

export function deactivate(): void {
  stop();
}
