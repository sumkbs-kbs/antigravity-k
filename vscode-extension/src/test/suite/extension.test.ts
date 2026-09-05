import * as http from 'node:http';
import * as assert from 'node:assert/strict';
import * as vscode from 'vscode';
import type { IdeSyncApi } from '../../extension';

type WireState = {
  readonly active_file: string;
  readonly cursor_line: number;
  readonly open_files: readonly string[];
};

type ReceivedRequest = {
  readonly method: string | undefined;
  readonly url: string | undefined;
  readonly state: WireState;
};

function parseState(value: unknown): WireState {
  assert.ok(typeof value === 'object' && value !== null);
  const record = value as Record<string, unknown>;
  assert.equal(typeof record.active_file, 'string');
  assert.equal(typeof record.cursor_line, 'number');
  assert.ok(Array.isArray(record.open_files));
  return {
    active_file: record.active_file as string,
    cursor_line: record.cursor_line as number,
    open_files: record.open_files as readonly string[],
  };
}

function listen(server: http.Server): Promise<void> {
  const port = Number(process.env.AGK_IDE_SYNC_TEST_PORT);
  assert.ok(Number.isInteger(port));
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => resolve());
  });
}

function closeServer(server: http.Server): Promise<void> {
  return new Promise((resolve, reject) => {
    server.close(error => {
      if (error === undefined) {
        resolve();
        return;
      }
      reject(error);
    });
  });
}

function collectRequests(target: ReceivedRequest[]): http.RequestListener {
  return (request, response) => {
    const chunks: Buffer[] = [];
    request.on('data', (chunk: Buffer) => {
      chunks.push(chunk);
    });
    request.on('end', () => {
      target.push({
        method: request.method,
        url: request.url,
        state: parseState(JSON.parse(Buffer.concat(chunks).toString('utf8'))),
      });
      response.writeHead(200, { 'Content-Type': 'application/json' });
      response.end('{"status":"ok"}');
    });
  };
}

function waitUntil(description: string, predicate: () => boolean): Promise<void> {
  return new Promise((resolve, reject) => {
    const interval = setInterval(() => {
      if (predicate()) {
        clearInterval(interval);
        clearTimeout(timeout);
        resolve();
      }
    }, 10);
    const timeout = setTimeout(() => {
      clearInterval(interval);
      reject(new Error(`Timed out waiting for ${description}`));
    }, 5000);
  });
}

function quietFor(milliseconds: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, milliseconds));
}

async function workspaceFile(name: string): Promise<vscode.Uri> {
  const folders = vscode.workspace.workspaceFolders;
  const folder = folders === undefined ? undefined : folders[0];
  assert.ok(folder !== undefined);
  return vscode.Uri.joinPath(folder.uri, name);
}

async function showFile(name: string, line: number): Promise<vscode.TextEditor> {
  const document = await vscode.workspace.openTextDocument(await workspaceFile(name));
  const editor = await vscode.window.showTextDocument(document, { preview: false });
  editor.selection = new vscode.Selection(line, 0, line, 0);
  return editor;
}

suite('Antigravity-K IDE Sync extension', () => {
  let api: IdeSyncApi;
  let server: http.Server | undefined;
  let requests: ReceivedRequest[] = [];

  suiteSetup(async () => {
    const extension = vscode.extensions.getExtension<IdeSyncApi>('antigravity-k.antigravity-k-sync');
    assert.ok(extension !== undefined, 'extension is not loaded by Extension Host');
    api = extension.isActive ? extension.exports : await extension.activate();
    assert.equal(typeof api.sendNow, 'function');
  });

  teardown(async () => {
    if (server !== undefined) {
      await closeServer(server);
      server = undefined;
    }
    requests = [];
  });

  test('manifest command is registered and returns status', async () => {
    const commands = await vscode.commands.getCommands(true);
    assert.ok(commands.includes('antigravity-k-sync.showStatus'));
    const commandResult = await vscode.commands.executeCommand<object>(
      'antigravity-k-sync.showStatus',
    );
    assert.ok(commandResult !== null && typeof commandResult === 'object');
    assert.ok('lastState' in commandResult);
    assert.ok('lastError' in commandResult);
  });

  test('offline activation is quiet, times out hanging endpoints, then reconnects', async () => {
    await showFile('sample.txt', 1);
    await waitUntil('offline error status', () => api.status.lastError !== null);

    const hangingServer = http.createServer((request, response) => {
      request.resume();
      response.once('close', () => undefined);
    });
    await listen(hangingServer);
    const editor = await showFile('sample.txt', 2);
    editor.selection = new vscode.Selection(3, 0, 3, 0);
    await waitUntil('request timeout error', () => api.status.lastError?.includes('timed out') === true);
    await closeServer(hangingServer);

    requests = [];
    await vscode.workspace.openTextDocument(await workspaceFile('other.txt'));
    server = http.createServer(collectRequests(requests));
    await listen(server);
    await showFile('sample.txt', 0);
    await waitUntil('reconnected request', () => requests.length >= 1);

    const request = requests[0];
    assert.equal(request.method, 'POST');
    assert.equal(request.url, '/update');
    assert.match(request.state.active_file, /sample\.txt$/);
    assert.ok(request.state.cursor_line >= 1);
    assert.ok(request.state.open_files.some(name => name.endsWith('other.txt')));
  });

  test('document changes are synced and rapid selection events are debounced', async () => {
    requests = [];
    server = http.createServer(collectRequests(requests));
    await listen(server);

    const editor = await showFile('sample.txt', 1);
    await waitUntil('initial selection request', () => requests.length >= 1);
    const beforeDocumentChange = requests.length;
    const edit = new vscode.WorkspaceEdit();
    edit.insert(editor.document.uri, new vscode.Position(4, 0), 'changed\n');
    assert.ok(await vscode.workspace.applyEdit(edit));
    await waitUntil('document change request', () => requests.length > beforeDocumentChange);
    assert.ok(requests.some(request => request.state.cursor_line === 2));

    const beforeFlood = requests.length;
    for (let index = 0; index < 60; index += 1) {
      const line = index % 4;
      editor.selection = new vscode.Selection(line, index % 3, line, index % 3);
    }
    await waitUntil('debounced flood request', () => requests.length > beforeFlood);
    await quietFor(500);
    assert.ok(
      requests.length - beforeFlood <= 5,
      `sent ${requests.length - beforeFlood} requests for 60 events`,
    );
  });

  test('deactivate stops pending and future sync requests', async () => {
    requests = [];
    server = http.createServer(collectRequests(requests));
    await listen(server);
    await showFile('sample.txt', 0);
    await waitUntil('request before deactivation', () => requests.length >= 1);
    await quietFor(300);
    const before = requests.length;

    api.stop();
    api.sendNow();
    await quietFor(500);
    assert.equal(requests.length, before);
    await new Promise(resolve => setTimeout(resolve, 120));
    assert.equal(requests.length, before);
  });
});
