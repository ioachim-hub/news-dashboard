// @vitest-environment happy-dom
import { describe, it, expect, beforeEach } from 'vitest';
import { detectPlatform } from '../lib/platform';

beforeEach(() => {
  // Clear electronAPI and sessionStorage between tests.
  delete (window as { electronAPI?: unknown }).electronAPI;
  sessionStorage.clear();
  // Reset referrer to empty (happy-dom allows setting it).
  Object.defineProperty(document, 'referrer', { value: '', configurable: true });
});

describe('detectPlatform', () => {
  it('returns "electron" when window.electronAPI is present', () => {
    (window as { electronAPI?: unknown }).electronAPI = { platform: 'electron' };
    expect(detectPlatform()).toBe('electron');
  });

  it('returns "twa" when referrer starts with android-app://', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'android-app://ro.lihor.newsdashboard/',
      configurable: true,
    });
    expect(detectPlatform()).toBe('twa');
  });

  it('caches twa in sessionStorage', () => {
    Object.defineProperty(document, 'referrer', {
      value: 'android-app://ro.lihor.newsdashboard/',
      configurable: true,
    });
    detectPlatform();
    // Clear referrer to simulate subsequent navigation.
    Object.defineProperty(document, 'referrer', { value: '', configurable: true });
    expect(detectPlatform()).toBe('twa');
  });

  it('returns "web" when no signals are present', () => {
    expect(detectPlatform()).toBe('web');
  });

  it('prefers electron over cached twa', () => {
    sessionStorage.setItem('nd_platform', 'twa');
    (window as { electronAPI?: unknown }).electronAPI = { platform: 'electron' };
    expect(detectPlatform()).toBe('electron');
  });
});
