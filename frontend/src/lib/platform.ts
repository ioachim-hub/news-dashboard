/** Which shell is the web app running inside. */
export type AppPlatform = 'electron' | 'twa' | 'web';

/** Detect the current platform once and cache in sessionStorage. */
export function detectPlatform(): AppPlatform {
  if (typeof window !== 'undefined' && 'electronAPI' in window) return 'electron';

  if (typeof sessionStorage !== 'undefined') {
    const cached = sessionStorage.getItem('nd_platform');
    if (cached === 'twa') return 'twa';

    // android-app:// referrer is set on the initial TWA navigation only.
    if (typeof document !== 'undefined' && document.referrer.startsWith('android-app://')) {
      sessionStorage.setItem('nd_platform', 'twa');
      return 'twa';
    }
  }

  return 'web';
}
