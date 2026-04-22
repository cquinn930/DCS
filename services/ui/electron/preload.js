/**
 * DCS Electron Preload Script
 * 
 * Exposes safe APIs to the renderer process.
 * Security: Only expose necessary functionality, no raw Node access.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose safe APIs to window.electronAPI
contextBridge.exposeInMainWorld('electronAPI', {
  // Get API URL from main process
  getApiUrl: () => ipcRenderer.invoke('get-api-url'),
  
  // Get app version
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  
  // Check if running in Electron
  isElectron: () => ipcRenderer.invoke('is-electron'),
  
  // System SSO login
  systemSsoLogin: () => ipcRenderer.invoke('system-sso-login'),
  
  // Platform info (for UI adjustments)
  platform: process.platform,
});
