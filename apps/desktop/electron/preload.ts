import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("jarvis", {
  config: {
    get: () => ipcRenderer.invoke("jarvis:v1:config:get"),
    set: (value: unknown) => ipcRenderer.invoke("jarvis:v1:config:set", value),
    reset: () => ipcRenderer.invoke("jarvis:v1:config:reset"),
  },
  app: {
    getVersion: () => ipcRenderer.invoke("jarvis:v1:app:getVersion"),
  },
});
