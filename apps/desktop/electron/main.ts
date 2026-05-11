import { app, BrowserWindow, ipcMain, shell } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  defaultJarvisConfig,
  jarvisConfigSchema,
  readConfig,
  writeConfig,
  type JarvisConfig,
} from "./config-store";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

process.env.APP_ROOT = path.join(__dirname, "..");

const isDev = !app.isPackaged;
let mainWindow: BrowserWindow | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    titleBarStyle: "hiddenInset",
    trafficLightPosition: { x: 16, y: 16 },
    backgroundColor: "#030712",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
    if (isDev && process.env.JARVIS_OPEN_DEVTOOLS === "1") {
      mainWindow?.webContents.openDevTools({ mode: "detach" });
    }
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    void mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    void mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

function registerIpc(): void {
  ipcMain.handle("jarvis:v1:config:get", (): JarvisConfig => {
    return readConfig(app.getPath("userData"));
  });

  ipcMain.handle("jarvis:v1:config:set", (_event, payload: unknown): JarvisConfig => {
    const next = jarvisConfigSchema.parse(payload);
    writeConfig(app.getPath("userData"), next);
    return next;
  });

  ipcMain.handle("jarvis:v1:config:reset", (): JarvisConfig => {
    const next = { ...defaultJarvisConfig };
    writeConfig(app.getPath("userData"), next);
    return next;
  });

  ipcMain.handle("jarvis:v1:app:getVersion", (): string => app.getVersion());
}

app.whenReady().then(() => {
  registerIpc();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

function openOAuthInSystemBrowser(url: string): boolean {
  try {
    const u = new URL(url);
    if (u.protocol !== "http:" && u.protocol !== "https:") {
      return false;
    }
    const host = u.hostname;
    if (host === "slack.com" || host.endsWith(".slack.com")) {
      return true;
    }
    if (u.pathname.includes("/slack/connect") || u.pathname.includes("/slack/oauth/")) {
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

app.on("web-contents-created", (_event, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    if (openOAuthInSystemBrowser(url)) {
      void shell.openExternal(url);
    }
    return { action: "deny" };
  });
  contents.on("will-navigate", (event, url) => {
    if (contents.getType() === "webview") return;
    const allowed =
      (process.env.VITE_DEV_SERVER_URL && url.startsWith(process.env.VITE_DEV_SERVER_URL)) ||
      url.startsWith("file://");
    if (!allowed) {
      event.preventDefault();
    }
  });
});
