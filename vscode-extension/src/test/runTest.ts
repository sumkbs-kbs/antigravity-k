import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { runTests, type TestOptions } from '@vscode/test-electron';

async function reservePort(): Promise<number> {
  const net = await import('node:net');
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (address === null || typeof address === 'string') {
        server.close(() => reject(new Error('Could not reserve a test port')));
        return;
      }
      const { port } = address;
      server.close(() => resolve(port));
    });
  });
}

async function main(): Promise<void> {
  const extensionDevelopmentPath = path.resolve(__dirname, '../..');
  const extensionTestsPath = path.resolve(__dirname, 'suite');
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'agk-ide-sync-'));
  const workspace = path.join(root, 'workspace');
  const userData = path.join(root, 'user-data');
  const extensions = path.join(root, 'extensions');
  const port = await reservePort();

  await fs.mkdir(path.join(workspace, '.vscode'), { recursive: true });
  await fs.mkdir(userData, { recursive: true });
  await fs.mkdir(extensions, { recursive: true });
  await fs.writeFile(path.join(workspace, 'sample.txt'), 'one\ntwo\nthree\nfour\n', 'utf8');
  await fs.writeFile(path.join(workspace, 'other.txt'), 'other file\n', 'utf8');
  await fs.writeFile(
    path.join(workspace, '.vscode', 'settings.json'),
    `${JSON.stringify(
      {
        'antigravityK.ideSync.port': port,
        'antigravityK.ideSync.debounceMilliseconds': 40,
        'antigravityK.ideSync.requestTimeoutMilliseconds': 400,
      },
      null,
      2,
    )}\n`,
    'utf8',
  );
  process.env.AGK_IDE_SYNC_TEST_PORT = String(port);

  const options: TestOptions = {
    extensionDevelopmentPath,
    extensionTestsPath,
    launchArgs: [
      workspace,
      `--user-data-dir=${userData}`,
      `--extensions-dir=${extensions}`,
      '--disable-extensions',
      '--disable-workspace-trust',
    ],
  };
  let codePath = process.env.AGK_VSCODE_PATH;
  if (!codePath) {
    const localAppMacOs = '/Applications/Visual Studio Code.app/Contents/MacOS';
    const localElectron = path.join(localAppMacOs, 'Electron');
    const localCode = path.join(localAppMacOs, 'Code');
    try {
      await fs.access(localElectron);
      codePath = localElectron;
    } catch {
      try {
        await fs.access(localCode);
        codePath = localCode;
      } catch {
        // Fall back to default @vscode/test-electron download
      }
    }
  }
  if (codePath !== undefined && codePath !== '') {
    options.vscodeExecutablePath = codePath;
  }
  options.extensionTestsEnv = {
    AGK_IDE_SYNC_TEST_PORT: String(port),
  };

  try {
    await runTests(options);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
}

void main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
