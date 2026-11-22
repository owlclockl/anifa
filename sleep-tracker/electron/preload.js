const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('sleepAPI', {
  load: () => ipcRenderer.invoke('sleep:load'),
  save: (data) => ipcRenderer.invoke('sleep:save', data),
  openExternal: (url) => ipcRenderer.invoke('sleep:open-external', url),
  isElectron: true,
});
