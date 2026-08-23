import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from '../../dashboard/node_modules/@playwright/test/index.mjs';

const readOption = (name) => {
  const index = process.argv.indexOf(name);
  if (index === -1) return undefined;
  return process.argv[index + 1];
};

const title = readOption('--title') ?? 'Terminal Visual QA';
const sourcePath = readOption('--from-file');
const evidenceDir = readOption('--evidence-dir');
const columns = Number.parseInt(readOption('--cols') ?? '100', 10);
const rows = Number.parseInt(readOption('--rows') ?? '32', 10);

if (sourcePath === undefined || evidenceDir === undefined) {
  throw new Error('Usage: --from-file <capture> --evidence-dir <dir> [--title <title>]');
}

const root = path.resolve(import.meta.dirname, '../..');
const xtermScript = path.join(root, 'dashboard/node_modules/xterm/lib/xterm.js');
const xtermStyles = path.join(root, 'dashboard/node_modules/xterm/css/xterm.css');
const capture = await fs.readFile(path.resolve(sourcePath), 'utf8');
const outputDir = path.resolve(evidenceDir);
await fs.mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ channel: 'chrome' });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.setContent(`
    <!doctype html>
    <html lang="ko">
      <head><meta charset="utf-8"><title>${title}</title></head>
      <body>
        <main>
          <h1>${title}</h1>
          <div id="terminal" aria-label="${title}"></div>
        </main>
      </body>
    </html>
  `);
  await page.addStyleTag({ path: xtermStyles });
  await page.addStyleTag({
    content: `
      :root { color-scheme: dark; }
      body { margin: 0; background: #080a0f; color: #e4e6eb; font-family: Inter, sans-serif; }
      main { width: fit-content; margin: 24px auto; }
      h1 { margin: 0 0 12px; font-size: 16px; font-weight: 600; }
      #terminal { padding: 12px; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; }
    `,
  });
  await page.addScriptTag({ path: xtermScript });
  await page.evaluate(
    ({ terminalCapture, terminalColumns, terminalRows }) => new Promise((resolve) => {
      const terminal = new window.Terminal({
        cols: terminalColumns,
        rows: terminalRows,
        convertEol: false,
        fontFamily: 'JetBrains Mono, Menlo, monospace',
        fontSize: 14,
        lineHeight: 1.15,
        theme: { background: '#0d1117', foreground: '#c9d1d9' },
      });
      terminal.open(document.querySelector('#terminal'));
      terminal.write(terminalCapture, resolve);
    }),
    { terminalCapture: capture, terminalColumns: columns, terminalRows: rows },
  );
  await page.locator('#terminal').screenshot({ path: path.join(outputDir, 'terminal.png') });
  const renderedText = await page.locator('.xterm-rows').innerText();
  await fs.writeFile(path.join(outputDir, 'terminal.txt'), renderedText, 'utf8');
  await fs.writeFile(path.join(outputDir, 'terminal-ansi.txt'), capture, 'utf8');
  await fs.writeFile(
    path.join(outputDir, 'metadata.json'),
    `${JSON.stringify({ title, columns, rows, sourcePath: path.resolve(sourcePath) }, null, 2)}\n`,
    'utf8',
  );
} finally {
  await browser.close();
}
