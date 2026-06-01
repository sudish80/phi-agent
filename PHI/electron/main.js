const { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage, Notification } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const http = require('http')

const SERVER_PORT = 8000
const SERVER_URL = `http://127.0.0.1:${SERVER_PORT}`
const BACKEND_DIR = path.resolve(__dirname, '..')
const FRONTEND_DIR = path.resolve(__dirname, '..', 'frontend', 'build')

let mainWindow = null
let tray = null
let pythonProcess = null
let serverReady = false
let isQuitting = false

function findPython() {
  const candidates = ['python', 'python3', 'py']
  for (const cmd of candidates) {
    try {
      const result = require('child_process').spawnSync(cmd, ['--version'], { stdio: 'pipe' })
      if (result.status === 0) return cmd
    } catch (_) {}
  }
  return 'python'
}

function startPythonServer() {
  const python = findPython()
  console.log(`Starting Python server with: ${python}`)

  pythonProcess = spawn(python, [
    '-m', 'uvicorn', 'backend.orchestrator.main:app',
    '--host', '127.0.0.1',
    '--port', String(SERVER_PORT),
    '--log-level', 'info',
    '--reload',
  ], {
    cwd: BACKEND_DIR,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  })

  pythonProcess.stdout.on('data', (data) => {
    const lines = data.toString().split('\n').filter(Boolean)
    lines.forEach(line => console.log(`[server] ${line}`))
    if (mainWindow) mainWindow.webContents.send('server:log', data.toString())
  })

  pythonProcess.stderr.on('data', (data) => {
    const text = data.toString()
    console.error(`[server:err] ${text}`)
    if (mainWindow) mainWindow.webContents.send('server:log', text)
  })

  pythonProcess.on('error', (err) => {
    console.error('Failed to start Python server:', err.message)
    showErrorNotification('Failed to start Python server: ' + err.message)
  })

  pythonProcess.on('exit', (code) => {
    console.log(`Python server exited with code ${code}`)
    pythonProcess = null
    serverReady = false
    if (!isQuitting) {
      setTimeout(startPythonServer, 3000)
    }
  })
}

function waitForServer() {
  return new Promise((resolve) => {
    const check = () => {
      const req = http.get(`${SERVER_URL}/health`, (res) => {
        let data = ''
        res.on('data', (chunk) => data += chunk)
        res.on('end', () => {
          serverReady = true
          updateTray()
          if (mainWindow) mainWindow.webContents.send('server:status-change', 'ready')
          resolve(true)
        })
      })
      req.on('error', () => {
        setTimeout(check, 500)
      })
      req.end()
    }
    check()
  })
}

function showErrorNotification(msg) {
  if (Notification.isSupported()) {
    new Notification({ title: 'PHI Agent', body: msg }).show()
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    frame: true,
    show: false,
    icon: require('fs').existsSync(path.join(__dirname, 'icon.png'))
      ? path.join(__dirname, 'icon.png')
      : undefined,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  if (require('fs').existsSync(path.join(FRONTEND_DIR, 'index.html'))) {
    mainWindow.loadFile(path.join(FRONTEND_DIR, 'index.html'))
  } else if (require('fs').existsSync(path.join(FRONTEND_DIR, 'chat.html'))) {
    mainWindow.loadFile(path.join(FRONTEND_DIR, 'chat.html'))
  } else {
    mainWindow.loadURL(`data:text/html,
      <html><body style="background:#0a0a1a;color:#00d4ff;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;flex-direction:column;gap:10px;">
      <h2>PHI Agent Desktop</h2>
      <p style="color:#666">Frontend build not found in: ${FRONTEND_DIR}</p>
      </body></html>`)
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault()
      mainWindow.hide()
    }
  })
}

function createTray() {
  const iconSize = 16
  const icon = nativeImage.createEmpty()
  tray = new Tray(icon)
  tray.setToolTip('PHI Agent')

  updateTray()
  tray.on('double-click', () => {
    if (mainWindow) mainWindow.show()
  })
}

function updateTray() {
  if (!tray) return
  const contextMenu = Menu.buildFromTemplate([
    {
      label: serverReady ? 'Server: Running' : 'Server: Starting...',
      enabled: false,
    },
    { type: 'separator' },
    {
      label: 'Show Window',
      click: () => { if (mainWindow) mainWindow.show() },
    },
    {
      label: 'Restart Server',
      click: () => restartServer(),
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true
        app.quit()
      },
    },
  ])
  tray.setContextMenu(contextMenu)
}

function restartServer() {
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM')
    pythonProcess = null
  }
  serverReady = false
  if (mainWindow) mainWindow.webContents.send('server:status-change', 'starting')
  startPythonServer()
  waitForServer()
}

// IPC handlers
ipcMain.handle('server:status', () => ({ ready: serverReady, url: SERVER_URL }))
ipcMain.handle('server:restart', () => restartServer())
ipcMain.on('window:minimize', () => { if (mainWindow) mainWindow.minimize() })
ipcMain.on('window:maximize', () => {
  if (mainWindow) mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize()
})
ipcMain.on('window:close', () => { if (mainWindow) mainWindow.close() })

app.whenReady().then(() => {
  startPythonServer()
  waitForServer()
  createWindow()
  createTray()

  app.on('activate', () => {
    if (mainWindow) mainWindow.show()
  })
})

app.on('before-quit', () => {
  isQuitting = true
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM')
    setTimeout(() => {
      if (pythonProcess) pythonProcess.kill('SIGKILL')
    }, 5000)
  }
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
