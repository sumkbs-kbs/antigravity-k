'use strict';

/**
 * Ssak-Ai thin desktop shell (Phase 2).
 * Loads the Host SPA over loopback. Does not expose Electron APIs to the page.
 *
 * Host lifecycle (owned child only):
 * - Soft-probe SSAK_HOST_URL; if up → use it, do not spawn (ownedHost=false).
 * - If down and SSAK_SPAWN_HOST≠0 (default spawn) → spawn Host as child;
 *   tray shows “Host starting…” until ready or timeout.
 * - Quit (tray / app) stops owned child only (SIGTERM → SIGKILL). Hide-on-close does not.
 * - Never kills unrelated PIDs / soak 29961·29969 / val02_staging.
 * - Tray “진단 내보내기…” → child_process `uv run agk diagnostics export` (same CLI).
 * - Host-fail → Phase 4 recovery dialog (logs / export / retry / browser / quit).
 * - Tray “업데이트 확인…” → soft check (SSAK_UPDATE_FEED); never auto-install.
 */

const fs = require('fs');
const path = require('path');
const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, shell } = require('electron');

const lifecycle = require('./hostLifecycle');
const updateChannels = require('./updateChannels');

const HOST_URL = lifecycle.resolveHostUrl();
const SPAWN_HOST = lifecycle.spawnHostEnabled();
/** SPA settings route (dashboard/src/App.tsx Route path="/settings"). */
const SETTINGS_PATH = '/settings';
/** Quiet Host status refresh — avoid probe spam. */
const HOST_STATUS_INTERVAL_MS = 120_000;
const HOST_START_TIMEOUT_MS = lifecycle.DEFAULT_START_TIMEOUT_MS;

/** @type {BrowserWindow | null} */
let mainWindow = null;
/** @type {Tray | null} */
let tray = null;
let quitting = false;
/** Last soft-probe result for tray status label. */
let hostReady = false;
/** True while owned spawn is in flight (tray “starting…”). */
let hostStarting = false;
/** True only when this process spawned the Host child. */
let ownedHost = false;
/** @type {import('child_process').ChildProcess | null} */
let hostChild = null;
/** @type {ReturnType<typeof setInterval> | null} */
let hostStatusTimer = null;
let hostStopInProgress = false;
/** True while tray diagnostics export child is running. */
let diagnosticsExportInFlight = false;
/** True while tray update soft-check is running. */
let updateCheckInFlight = false;
/** Recent owned-Host stderr (for EADDRINUSE / recovery hints). */
let hostRecentStderr = '';
/** Last ensureHost failure context for recovery copy. */
let lastEnsureMeta = { reason: '', spawnLabel: '', error: '' };
/** Guard overlapping recovery dialogs. */
let recoveryDialogOpen = false;

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    showMainWindow();
  });
}

function settingsUrl() {
  return `${HOST_URL}${SETTINGS_PATH}`;
}

/** macOS: ~/Library/Logs/Ssak-Ai (MACOS_DMG_GUIDE). Other: ~/.antigravity-k/logs. */
function logsDir() {
  if (process.platform === 'darwin') {
    return path.join(app.getPath('home'), 'Library', 'Logs', 'Ssak-Ai');
  }
  return path.join(app.getPath('home'), '.antigravity-k', 'logs');
}

function ensureLogsDir() {
  const dir = logsDir();
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function trayStatusLabel() {
  if (hostStarting) return 'Host starting…';
  if (hostReady) return 'Host ready';
  return 'Host unreachable';
}

function trayIcon() {
  const iconPath = path.join(__dirname, 'assets', 'tray.png');
  let image = nativeImage.createFromPath(iconPath);
  if (image.isEmpty()) {
    // 16x16 fallback (transparent) — macOS still shows a blank tray slot
    image = nativeImage.createEmpty();
  }
  if (process.platform === 'darwin') {
    image = image.resize({ width: 18, height: 18 });
    try {
      image.setTemplateImage(true);
    } catch {
      /* older Electron */
    }
  }
  return image;
}

function buildTrayMenu() {
  return Menu.buildFromTemplate([
    {
      label: trayStatusLabel(),
      enabled: false,
    },
    { type: 'separator' },
    {
      label: 'Open',
      click: () => showMainWindow(),
    },
    {
      label: 'Settings',
      click: () => openSettings(),
    },
    {
      label: 'Open in Browser',
      click: () => {
        shell.openExternal(HOST_URL).catch(() => {});
      },
    },
    {
      label: 'Open logs folder',
      click: () => openLogsFolder(),
    },
    {
      label: '진단 내보내기…',
      enabled: !diagnosticsExportInFlight,
      click: () => {
        exportDiagnosticsFromTray().catch((err) => {
          console.error('[ssak-desktop] diagnostics export failed:', err);
        });
      },
    },
    {
      label: '업데이트 확인…',
      enabled: !updateCheckInFlight,
      click: () => {
        checkForUpdatesFromTray().catch((err) => {
          console.error('[ssak-desktop] update check failed:', err);
        });
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        quitting = true;
        app.quit();
      },
    },
  ]);
}

function refreshTrayMenu() {
  if (!tray) return;
  try {
    tray.setContextMenu(buildTrayMenu());
  } catch (err) {
    console.error('[ssak-desktop] refreshTrayMenu failed:', err);
  }
}

async function refreshHostStatus() {
  if (hostStarting) {
    refreshTrayMenu();
    return;
  }
  hostReady = await lifecycle.hostProbe(HOST_URL);
  refreshTrayMenu();
}

function createTray() {
  tray = new Tray(trayIcon());
  tray.setToolTip('Ssak-Ai');
  refreshTrayMenu();
  tray.on('click', () => showMainWindow());
  tray.on('double-click', () => showMainWindow());
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 800,
    minHeight: 560,
    show: false,
    title: 'Ssak-Ai',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      // No preload bridge — page must not gain Electron/Node APIs
      preload: undefined,
    },
  });

  mainWindow.once('ready-to-show', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show();
    }
  });

  // Hide-on-close: window close keeps process + tray alive (owned Host stays up)
  mainWindow.on('close', (event) => {
    if (!quitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  mainWindow.loadURL(HOST_URL).catch((err) => {
    console.error('[ssak-desktop] loadURL failed:', err);
  });
}

function showMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    createMainWindow();
    return;
  }
  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  mainWindow.show();
  mainWindow.focus();
}

function openSettings() {
  showMainWindow();
  if (!mainWindow || mainWindow.isDestroyed()) return;
  mainWindow.loadURL(settingsUrl()).catch((err) => {
    console.error('[ssak-desktop] Settings loadURL failed:', err);
  });
}

function openLogsFolder() {
  try {
    const dir = ensureLogsDir();
    shell.openPath(dir).then((errMsg) => {
      if (errMsg) {
        console.error('[ssak-desktop] openPath logs failed:', errMsg);
        dialog.showErrorBox('Open logs folder', `Could not open:\n${dir}\n\n${errMsg}`);
      }
    });
  } catch (err) {
    console.error('[ssak-desktop] ensureLogsDir failed:', err);
    dialog.showErrorBox(
      'Open logs folder',
      `Could not create or open logs directory:\n${logsDir()}\n\n${err && err.message ? err.message : err}`,
    );
  }
}


function diagnosticsDefaultZipPath() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const localStamp =
    `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}` +
    `-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  return path.join(ensureLogsDir(), `diagnostics-${localStamp}.zip`);
}

/**
 * Tray “업데이트 확인…” — Phase 5 soft check only.
 * Unset SSAK_UPDATE_FEED → “업데이트 서버 미구성” (not a crash).
 * Never auto-downloads or installs.
 */
async function checkForUpdatesFromTray() {
  if (updateCheckInFlight) {
    dialog.showMessageBox({
      type: 'info',
      title: '업데이트 확인',
      message: '업데이트 확인이 이미 진행 중입니다.',
      buttons: ['OK'],
    });
    return;
  }

  updateCheckInFlight = true;
  refreshTrayMenu();

  try {
    const pkgVersion =
      (typeof app.getVersion === 'function' && app.getVersion()) ||
      require('./package.json').version ||
      '0.0.0';
    const result = await updateChannels.softCheckForUpdates({
      channel: 'stable',
      currentVersion: pkgVersion,
    });

    if (result.status === 'unconfigured') {
      dialog.showMessageBox({
        type: 'info',
        title: '업데이트 확인',
        message: '업데이트 서버 미구성',
        detail:
          `환경 변수 ${updateChannels.UPDATE_FEED_ENV}가 비어 있습니다.\n` +
          '개인용 GitHub Releases stub 피드를 설정하기 전까지는 확인만 가능합니다.\n' +
          '자동 설치는 기본 비활성입니다. 자세한 내용: docs/packaging/UPDATE_CHANNELS.md',
        buttons: ['OK'],
      });
      return;
    }

    const type =
      result.status === 'error' ? 'warning' : result.status === 'ok' ? 'info' : 'info';
    const detailParts = [
      result.channel ? `Channel: ${result.channel}` : null,
      result.feed && result.feed.version ? `Feed version: ${result.feed.version}` : null,
      result.code ? `Code: ${result.code}` : null,
      'Auto-install: off (this soft check never downloads).',
    ].filter(Boolean);
    dialog.showMessageBox({
      type,
      title: '업데이트 확인',
      message: result.userMessage || 'Update check finished',
      detail: detailParts.join('\n'),
      buttons: ['OK'],
    });
  } catch (err) {
    console.error('[ssak-desktop] checkForUpdatesFromTray:', err);
    dialog.showMessageBox({
      type: 'warning',
      title: '업데이트 확인',
      message: '업데이트 확인 중 오류가 발생했습니다',
      detail: err && err.message ? err.message : String(err),
      buttons: ['OK'],
    });
  } finally {
    updateCheckInFlight = false;
    refreshTrayMenu();
  }
}

/**
 * Tray “진단 내보내기…” — same path as `agk diagnostics export` via child_process
 * (uv run agk … / venv fallbacks). Does not block the UI event loop.
 */
async function exportDiagnosticsFromTray() {

  if (diagnosticsExportInFlight) {
    dialog.showMessageBox({
      type: 'info',
      title: 'Export diagnostics',
      message: 'Diagnostics export is already running.',
      detail: 'Wait for the current export to finish.',
      buttons: ['OK'],
    });
    return;
  }

  diagnosticsExportInFlight = true;
  refreshTrayMenu();

  const outPath = diagnosticsDefaultZipPath();
  console.log(`[ssak-desktop] diagnostics export → ${outPath}`);

  try {
    const result = await lifecycle.runDiagnosticsExport({
      repoRoot: lifecycle.resolveRepoRoot(__dirname),
      outputPath: outPath,
      timeoutMs: 120_000,
    });

    if (result.ok && result.zipPath) {
      const zipPath = result.zipPath;
      const revealLabel =
        process.platform === 'darwin' ? 'Show in Finder' : 'Show in folder';
      const choice = dialog.showMessageBoxSync({
        type: 'info',
        title: 'Export diagnostics',
        message: 'Diagnostics ZIP ready',
        detail: zipPath,
        buttons: [revealLabel, 'OK'],
        defaultId: 0,
        cancelId: 1,
      });
      if (choice === 0) {
        try {
          shell.showItemInFolder(zipPath);
        } catch (err) {
          console.error('[ssak-desktop] showItemInFolder failed:', err);
        }
      }
      return;
    }

    const detailParts = [
      result.label ? `Command:\n  ${result.label}` : null,
      result.error ? `Error:\n  ${result.error}` : null,
      result.stderr ? `stderr:\n${result.stderr.slice(0, 1200)}` : null,
      `Tried output:\n  ${outPath}`,
    ].filter(Boolean);
    dialog.showErrorBox(
      'Export diagnostics failed',
      detailParts.join('\n\n') || 'Unknown diagnostics export failure.',
    );
  } catch (err) {
    dialog.showErrorBox(
      'Export diagnostics failed',
      err && err.message ? err.message : String(err),
    );
  } finally {
    diagnosticsExportInFlight = false;
    refreshTrayMenu();
  }
}

function startHostStatusPolling() {
  if (hostStatusTimer) return;
  hostStatusTimer = setInterval(() => {
    refreshHostStatus().catch(() => {});
  }, HOST_STATUS_INTERVAL_MS);
  // Allow process to exit on Quit without waiting for the timer
  if (typeof hostStatusTimer.unref === 'function') {
    hostStatusTimer.unref();
  }
}

function attachHostChildLogging(child) {
  const prefix = '[ssak-desktop:host]';
  if (child.stdout) {
    child.stdout.on('data', (buf) => {
      const line = String(buf).trim();
      if (line) console.log(prefix, line.slice(0, 400));
    });
  }
  if (child.stderr) {
    child.stderr.on('data', (buf) => {
      const raw = String(buf);
      hostRecentStderr = (hostRecentStderr + raw).slice(-4000);
      const line = raw.trim();
      if (line) console.error(prefix, line.slice(0, 400));
    });
  }
  child.on('exit', (code, signal) => {
    console.error(`[ssak-desktop] owned Host exited code=${code} signal=${signal}`);
    if (hostChild === child) {
      hostChild = null;
      if (!quitting) {
        ownedHost = false;
        hostStarting = false;
        hostReady = false;
        refreshTrayMenu();
      }
    }
  });
}

/**
 * @returns {Promise<'ready' | 'timeout' | 'spawn-failed' | 'unreachable'>}
 */
async function ensureHost() {
  hostReady = await lifecycle.hostProbe(HOST_URL);
  if (hostReady) {
    ownedHost = false;
    hostStarting = false;
    lastEnsureMeta = { reason: '', spawnLabel: '', error: '' };
    console.log(`[ssak-desktop] Host already reachable at ${HOST_URL}; not spawning`);
    return 'ready';
  }

  if (!SPAWN_HOST) {
    lastEnsureMeta = {
      reason: 'unreachable',
      spawnLabel: '',
      error: 'SSAK_SPAWN_HOST=0 (spawn disabled)',
    };
    return 'unreachable';
  }

  let spec;
  try {
    const bind = lifecycle.parseHostBind(HOST_URL);
    hostStarting = true;
    ownedHost = true;
    hostRecentStderr = '';
    refreshTrayMenu();

    const spawned = lifecycle.spawnOwnedHost({
      hostname: bind.hostname,
      port: bind.port,
      repoRoot: lifecycle.resolveRepoRoot(__dirname),
    });
    hostChild = spawned.child;
    spec = spawned.spec;
    console.log(`[ssak-desktop] spawning owned Host: ${spec.label} (pid pending)`);
    attachHostChildLogging(hostChild);

    if (!hostChild.pid) {
      await lifecycle.sleep(50);
    }
    console.log(`[ssak-desktop] owned Host pid=${hostChild.pid} via ${spec.label}`);

    if (lifecycle.FORBIDDEN_PIDS.has(hostChild.pid)) {
      console.error('[ssak-desktop] spawned pid collides with forbidden soak pid — aborting ownership');
      ownedHost = false;
      hostChild = null;
      hostStarting = false;
      lastEnsureMeta = {
        reason: 'spawn-failed',
        spawnLabel: spec.label,
        error: 'Spawned pid collides with forbidden soak pid',
      };
      return 'spawn-failed';
    }
  } catch (err) {
    hostStarting = false;
    ownedHost = false;
    hostChild = null;
    const errMsg = err && err.message ? err.message : String(err);
    console.error('[ssak-desktop] Host spawn failed:', err);
    lastEnsureMeta = {
      reason: 'spawn-failed',
      spawnLabel: '',
      error: errMsg,
    };
    return 'spawn-failed';
  }

  const ok = await lifecycle.waitForHostReady(HOST_URL, HOST_START_TIMEOUT_MS, {
    shouldAbort: () => quitting || !lifecycle.isChildAlive(hostChild),
  });

  hostStarting = false;
  hostReady = ok;
  refreshTrayMenu();

  if (!ok) {
    lastEnsureMeta = {
      reason: 'timeout',
      spawnLabel: spec.label,
      error: `Host did not become reachable within ~${Math.round(HOST_START_TIMEOUT_MS / 1000)}s`,
    };
    return 'timeout';
  }

  lastEnsureMeta = { reason: '', spawnLabel: '', error: '' };
  return 'ready';
}

/**
 * Stop owned child (if any) then re-run ensureHost when spawn is allowed;
 * otherwise soft-probe the existing SSAK_HOST_URL only.
 * @returns {Promise<'ready' | 'timeout' | 'spawn-failed' | 'unreachable'>}
 */
async function retryHostStart() {
  if (SPAWN_HOST) {
    if (ownedHost && lifecycle.isChildAlive(hostChild)) {
      console.log('[ssak-desktop] recovery Retry: stopping owned Host before re-spawn');
      await lifecycle.stopOwnedHost(hostChild, {
        graceMs: lifecycle.DEFAULT_STOP_GRACE_MS,
        log: (msg) => console.error(`[ssak-desktop] ${msg}`),
      });
    }
    hostChild = null;
    ownedHost = false;
    hostStarting = false;
    hostReady = false;
    hostRecentStderr = '';
    refreshTrayMenu();
    return ensureHost();
  }

  hostStarting = false;
  hostReady = await lifecycle.hostProbe(HOST_URL);
  refreshTrayMenu();
  if (hostReady) {
    lastEnsureMeta = { reason: '', spawnLabel: '', error: '' };
    return 'ready';
  }
  lastEnsureMeta = {
    reason: 'unreachable',
    spawnLabel: '',
    error: 'SSAK_SPAWN_HOST=0 — re-probed existing URL; still unreachable',
  };
  return 'unreachable';
}

/**
 * Phase 4 recovery UI — Electron dialog (no remote HTML).
 * Buttons: Open logs / Export diagnostics / Retry / Open in browser / Quit.
 * @param {{ reason: string }} opts
 * @returns {Promise<'retry' | 'open-browser' | 'quit'>}
 */
async function showHostRecoveryDialog(opts) {
  const reason = opts.reason || lastEnsureMeta.reason || 'timeout';
  const portConflict = await lifecycle.suspectPortConflict(HOST_URL, {
    stderrHint: hostRecentStderr,
    errorHint: lastEnsureMeta.error || '',
  });

  let headline = 'Host did not become ready';
  if (reason === 'spawn-failed') headline = 'Host spawn failed';
  if (reason === 'unreachable') headline = 'Host loopback URL unreachable';

  const detailParts = [
    `URL: ${HOST_URL}`,
    lastEnsureMeta.error ? `Detail: ${lastEnsureMeta.error}` : null,
    lastEnsureMeta.spawnLabel ? `Spawn command:\n  ${lastEnsureMeta.spawnLabel}` : null,
    !SPAWN_HOST
      ? 'Spawn is disabled (SSAK_SPAWN_HOST=0). Retry only re-probes the URL — start Host yourself or set SSAK_SPAWN_HOST=1.'
      : 'Retry will stop any owned Host child and re-run spawn/probe.',
    portConflict
      ? 'Port conflict suspected: another process may already be using this port. Stop the other listener, change SSAK_HOST_URL / --port, then Retry. Check logs for EADDRINUSE / “address already in use” (Phase 4/6).'
      : null,
    'Open logs folder → ~/Library/Logs/Ssak-Ai (or ~/.antigravity-k/logs).',
    'Export diagnostics uses the same allowlist ZIP path as the tray item.',
  ].filter(Boolean);

  const detail = detailParts.join('\n\n');

  if (recoveryDialogOpen) {
    console.warn('[ssak-desktop] recovery dialog already open; skipping');
    return 'quit';
  }
  recoveryDialogOpen = true;
  try {
    for (;;) {
      if (quitting) return 'quit';
      const choice = dialog.showMessageBoxSync({
        type: 'warning',
        title: 'Ssak-Ai Host recovery',
        message: headline,
        detail,
        buttons: [
          'Open logs folder',
          'Export diagnostics',
          'Retry start',
          'Open in browser',
          'Quit',
        ],
        defaultId: 2,
        cancelId: 4,
        noLink: true,
      });

      if (choice === 0) {
        openLogsFolder();
        continue;
      }
      if (choice === 1) {
        await exportDiagnosticsFromTray();
        continue;
      }
      if (choice === 2) return 'retry';
      if (choice === 3) {
        shell.openExternal(HOST_URL).catch(() => {});
        return 'open-browser';
      }
      return 'quit';
    }
  } finally {
    recoveryDialogOpen = false;
  }
}

async function bootstrap() {
  let result = await ensureHost();

  while (result !== 'ready') {
    const action = await showHostRecoveryDialog({ reason: result });
    if (action === 'quit') {
      quitting = true;
      app.quit();
      return;
    }
    if (action === 'open-browser') {
      // Proceed to tray + window (loadURL may still fail; user can Retry from a later fail path via relaunch).
      break;
    }
    // retry
    result = await retryHostStart();
  }

  if (!tray) createTray();
  else refreshTrayMenu();
  createMainWindow();
  startHostStatusPolling();
}

app.whenReady().then(() => {
  if (process.platform === 'darwin') {
    app.dock?.show();
  }
  // Tray early so “starting…” is visible during owned spawn wait
  createTray();
  return bootstrap();
});

app.on('activate', () => {
  showMainWindow();
});

app.on('before-quit', (event) => {
  quitting = true;
  if (hostStatusTimer) {
    clearInterval(hostStatusTimer);
    hostStatusTimer = null;
  }

  if (ownedHost && lifecycle.isChildAlive(hostChild) && !hostStopInProgress) {
    event.preventDefault();
    hostStopInProgress = true;
    lifecycle
      .stopOwnedHost(hostChild, {
        graceMs: lifecycle.DEFAULT_STOP_GRACE_MS,
        log: (msg) => console.error(`[ssak-desktop] ${msg}`),
      })
      .finally(() => {
        ownedHost = false;
        hostChild = null;
        app.exit(0);
      });
  }
});

app.on('window-all-closed', () => {
  // Keep running for tray on all platforms until Quit
});
