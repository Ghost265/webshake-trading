const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('webshakeWindow', {
  minimize: () => ipcRenderer.invoke('window:minimize'),
  maximize: () => ipcRenderer.invoke('window:maximize'),
  close: () => ipcRenderer.invoke('window:close'),
  shutdown: () => ipcRenderer.invoke('app:shutdown'),
  restart: () => ipcRenderer.invoke('app:restart'),
  updateRestart: () => ipcRenderer.invoke('app:updateRestart')
});
