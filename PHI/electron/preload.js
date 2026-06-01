const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('phi', {
  getServerUrl: () => 'http://127.0.0.1:8000',
  getWsUrl: () => 'ws://127.0.0.1:8000/ws',
  getVisionUrl: () => 'http://127.0.0.1:8001',
  getSpeechUrl: () => 'http://127.0.0.1:8003',
  getHearingUrl: () => 'http://127.0.0.1:8002',
  getActionUrl: () => 'http://127.0.0.1:8004',
  serverStatus: () => ipcRenderer.invoke('server:status'),
  restartServer: () => ipcRenderer.invoke('server:restart'),
  onServerStatusChange: (cb) => {
    ipcRenderer.on('server:status-change', (_, status) => cb(status))
  },
  onServerLog: (cb) => {
    ipcRenderer.on('server:log', (_, msg) => cb(msg))
  },
  window: {
    minimize: () => ipcRenderer.send('window:minimize'),
    maximize: () => ipcRenderer.send('window:maximize'),
    close: () => ipcRenderer.send('window:close'),
  },
})
