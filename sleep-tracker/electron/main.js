const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const dataFile = () => path.join(app.getPath('userData'), 'notes.json');
ipcMain.handle('notes:load', () => {
  try { return fs.existsSync(dataFile()) ? JSON.parse(fs.readFileSync(dataFile(), 'utf8')) : null; }
  catch (err) { console.error(err); throw err; }
});
ipcMain.handle('notes:save', (_event, data) => {
  try { fs.mkdirSync(path.dirname(dataFile()), { recursive: true }); fs.writeFileSync(dataFile(), JSON.stringify(data, null, 2), 'utf8'); return true; }
  catch (err) { console.error(err); return false; }
});
function createWindow() {
  const win = new BrowserWindow({ width: 1280, height: 840, minWidth: 760, minHeight: 580, backgroundColor: '#fafaf7', title: 'Тихие заметки', webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false } });
  if (!app.isPackaged) win.loadURL('http://localhost:5174'); else win.loadFile(path.join(__dirname, '../dist/index.html'));
}
app.whenReady().then(() => { createWindow(); app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); }); });
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
