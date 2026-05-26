const { app, BrowserWindow, ipcMain } = require('electron');
const { exec, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

let mainWindow;
const ROOT_DIR = path.resolve(__dirname, '..', '..');
const STATE_FILE = path.join(ROOT_DIR, 'userdata', 'window_state.json');

function readWindowState() {
  try {
    if (!fs.existsSync(STATE_FILE)) return null;
    return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
  } catch { return null; }
}

function saveWindowState() {
  try {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    const bounds = mainWindow.getBounds();
    const state = { ...bounds, maximized: mainWindow.isMaximized(), saved_at: new Date().toISOString() };
    fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
    fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
  } catch {}
}

function createWindow() {
  const state = readWindowState();
  mainWindow = new BrowserWindow({
    width: state?.width || 1280,
    height: state?.height || 760,
    x: state?.x,
    y: state?.y,
    minWidth: 1050,
    minHeight: 650,
    backgroundColor: '#0b2d46',
    title: 'Webshake-Trading | v0.1.1-beta',
    frame: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });
  if (state?.maximized) mainWindow.maximize();
  mainWindow.loadURL('http://127.0.0.1:5173');
  mainWindow.on('resize', saveWindowState);
  mainWindow.on('move', saveWindowState);
  mainWindow.on('maximize', saveWindowState);
  mainWindow.on('unmaximize', saveWindowState);
  mainWindow.on('close', saveWindowState);
}

function logShutdown(reason = 'normal') {
  return new Promise((resolve) => {
    try {
      const req = require('http').request({ hostname: '127.0.0.1', port: 8765, path: `/api/system/shutdown-log?reason=${encodeURIComponent(reason)}`, method: 'POST', timeout: 900 }, () => resolve());
      req.on('error', () => resolve());
      req.on('timeout', () => { req.destroy(); resolve(); });
      req.end();
    } catch { resolve(); }
  });
}

async function gracefulShutdown(reason = 'normal') {
  saveWindowState();
  await logShutdown(reason);
  try {
    exec('taskkill /F /FI "WINDOWTITLE eq Webshake Electron" /T');
    exec('taskkill /F /FI "WINDOWTITLE eq Webshake Vite" /T');
    exec('taskkill /F /FI "WINDOWTITLE eq Webshake Backend" /T');
  } catch (e) {}
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.close();
  setTimeout(() => app.quit(), 250);
}


async function restartOnly() {
  saveWindowState?.();
  await logShutdown('restart-only');
  const script = path.join(ROOT_DIR, 'restart_webshake.bat');
  try {
    spawn('cmd.exe', ['/c', script], { cwd: ROOT_DIR, detached: true, stdio: 'ignore', windowsHide: true }).unref();
  } catch (e) {
    exec(`start "Webshake Restart" "${script}"`, { cwd: ROOT_DIR });
  }
  setTimeout(() => {
    try { if (mainWindow && !mainWindow.isDestroyed()) mainWindow.destroy(); } catch {}
    app.quit();
    process.exit(0);
  }, 500);
}

async function updateRestart() {
  saveWindowState();
  await logShutdown('update-restart');
  const script = path.join(ROOT_DIR, 'update_restart.bat');
  try {
    spawn('cmd.exe', ['/c', script], { cwd: ROOT_DIR, detached: true, stdio: 'ignore', windowsHide: true }).unref();
  } catch (e) {
    exec(`start "Webshake Update-Restart" "${script}"`, { cwd: ROOT_DIR });
  }
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.close();
  setTimeout(() => app.quit(), 200);
}

ipcMain.handle('window:minimize', () => mainWindow?.minimize());
ipcMain.handle('window:maximize', () => {
  if (!mainWindow) return;
  if (mainWindow.isMaximized()) mainWindow.unmaximize();
  else mainWindow.maximize();
});
ipcMain.handle('window:close', () => mainWindow?.close());
ipcMain.handle('app:shutdown', () => gracefulShutdown('normal'));
ipcMain.handle('app:restart', () => restartOnly());
ipcMain.handle('app:updateRestart', () => updateRestart());

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
