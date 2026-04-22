/**
 * Electron integration utilities
 *
 * Provides safe access to Electron APIs when running in desktop mode.
 * In web mode, these functions return appropriate defaults.
 */

interface ElectronAPI {
  getApiUrl: () => Promise<string>;
  getAppVersion: () => Promise<string>;
  isElectron: () => Promise<boolean>;
  systemSsoLogin: () => Promise<{ success: boolean; message?: string }>;
  platform: string;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

/**
 * Check if running in Electron
 */
export function isElectron(): boolean {
  return typeof window !== 'undefined' && !!window.electronAPI;
}

/**
 * Get API URL from Electron or environment
 */
export async function getApiUrl(): Promise<string> {
  if (isElectron()) {
    return window.electronAPI!.getApiUrl();
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
}

/**
 * Get app version
 */
export async function getAppVersion(): Promise<string> {
  if (isElectron()) {
    return window.electronAPI!.getAppVersion();
  }
  return process.env.NEXT_PUBLIC_APP_VERSION || '0.1.0';
}

/**
 * Get current platform
 */
export function getPlatform(): string {
  if (isElectron()) {
    return window.electronAPI!.platform;
  }
  return 'web';
}

/**
 * Attempt system SSO login (Electron only)
 */
export async function systemSsoLogin(): Promise<{
  success: boolean;
  message?: string;
}> {
  if (isElectron()) {
    return window.electronAPI!.systemSsoLogin();
  }
  return { success: false, message: 'SSO only available in desktop app' };
}
