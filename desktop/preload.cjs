'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('palimpsest', Object.freeze({
  request: payload => ipcRenderer.invoke('palimpsest:request', payload),
  stores: () => ipcRenderer.invoke('palimpsest:stores'),
  connection: storeId => ipcRenderer.invoke('palimpsest:connection', storeId),
  reconnect: storeId => ipcRenderer.invoke('palimpsest:reconnect', storeId),
  realms: payload => ipcRenderer.invoke('palimpsest:realms', payload),
}));
