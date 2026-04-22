/**
 * DCS Electron Main Process
 *
 * Security requirements:
 * - Use system SSO (no embedded credentials)
 * - No embedded secrets
 * - Secure IPC communication
 * - Electron 41+ security defaults
 */

const { app, BrowserWindow, ipcMain, session } = require('electron');
const path = require('path');

app.disableHardwareAcceleration();

const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
}

let mainWindow = null;

const API_URL = process.env.DCS_API_URL || 'http://localhost:8000';
const WEB_URL = process.env.DCS_WEB_URL || 'http://localhost:3000';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    title: 'DCS - Debt Collection System',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: path.join(__dirname, 'preload.js'),
      spellcheck: false,
    },
    autoHideMenuBar: true,
  });

  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'",
          `connect-src 'self' ${API_URL} ws://localhost:3000`,
          "script-src 'self'",
          "style-src 'self' 'unsafe-inline'",
          "img-src 'self' data: https:",
          "font-src 'self' data:",
        ].join('; '),
      },
    });
  });

  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL(WEB_URL);
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../out/index.html'));
  }

  mainWindow.webContents.on('will-navigate', (event, url) => {
    const allowedOrigins = [WEB_URL, API_URL, 'file://'];
    const isAllowed = allowedOrigins.some((origin) => url.startsWith(origin));
    if (!isAllowed) {
      event.preventDefault();
    }
  });

  mainWindow.webContents.setWindowOpenHandler(() => {
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

ipcMain.handle('get-api-url', () => API_URL);
ipcMain.handle('get-app-version', () => app.getVersion());
ipcMain.handle('is-electron', () => true);

ipcMain.handle('system-sso-login', async () => {
  return {
    success: false,
    message: 'SSO not configured. Please use web login.',
  };
});
