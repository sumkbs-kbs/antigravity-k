'use strict';

/**
 * Ssak-Ai thin desktop shell (Phase 2 scaffold).
 * Loads the Host SPA over loopback. Does not expose Electron APIs to the page.
 * Host spawn/stop is NOT wired this turn — assume Host already running.
 */

const fs = require('fs');
const path = require('path');
const http = require('http');
const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, shell } = require('electron');

const DEFAULT_HOST_URL = 'http://127.0.0.1:8000';
const HOST_URL = (process.env.SSAK_HOST_URL || DEFAULT_HOST_URL).replace(/\/$/, '');
/** SPA settings route (dashboard/src/App.tsx Route path="/settings"). */
const SETTINGS_PATH = '/settings';
/** Quiet Host status refresh — avoid probe spam. */
const HOST_STATUS_INTERVAL_MS = 120_000;

/** @type {BrowserWindow | null} */
let mainWindow = null;
/** @type {Tray | null} */
let tray = null;
let quitting = false;
/** Last soft-probe result for tray status label. */
let hostReady = false;
/** @type {ReturnType<typeof setInterval> | null} */
let hostStatusTimer = null;

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    showMainWindow();
  });
}

function hostProbe(url, timeoutMs = 2000) {
  return new Promise((resolve) => {
    let settled = false;
    const done = (ok) => {
      if (settled) return;
      settled = true;
      resolve(ok);
    };
    try {
      const req = http.get(url, { timeout: timeoutMs }, (res) => {
        res.resume();
        done((res.statusCode || 0) >= 200 && (res.statusCode || 0) < 500);
      });
      req.on('error', () => done(false));
      req.on('timeout', () => {
        req.destroy();
        done(false);
      });
    } catch {
      done(false);
    }
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
      label: hostReady ? 'Host ready' : 'Host unreachable',
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
  hostReady = await hostProbe(HOST_URL);
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

  // Hide-on-close stub: window close keeps process + tray alive (Host untouched)
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

async function bootstrap() {
  // Soft probe — do not start Host (Phase 2; soak/:8000 safety)
  hostReady = await hostProbe(HOST_URL);
  if (!hostReady) {
    const detail =
      `Host does not appear to be reachable at ${HOST_URL}.\n\n` +
      'This shell does not spawn Host yet (Phase 2 scaffold).\n' +
      'Start Host first, e.g.:\n' +
      '  uv run agk serve --host 127.0.0.1 --port 8000\n' +
      '  or: make serve / existing launcher\n\n' +
      'Then re-open from the tray, or Quit and relaunch the shell.';
    const choice = dialog.showMessageBoxSync({
      type: 'warning',
      title: 'Ssak-Ai Host not ready',
      message: 'Host loopback URL unreachable',
      detail,
      buttons: ['Continue anyway', 'Quit'],
      defaultId: 0,
      cancelId: 1,
    });
    if (choice === 1) {
      quitting = true;
      app.quit();
      return;
    }
  }

  createTray();
  createMainWindow();
  startHostStatusPolling();
}

app.whenReady().then(() => {
  if (process.platform === 'darwin') {
    app.dock?.show();
  }
  return bootstrap();
});

app.on('activate', () => {
  showMainWindow();
});

app.on('before-quit', () => {
  quitting = true;
  if (hostStatusTimer) {
    clearInterval(hostStatusTimer);
    hostStatusTimer = null;
  }
  // Host stop intentionally NOT implemented this turn (C-03: do not disturb :8000 soak)
});

app.on('window-all-closed', () => {
  // Keep running for tray on all platforms until Quit
});
