/**
 * Compare two semver strings (major.minor.patch).
 * Returns  1 if a > b, -1 if a < b, 0 if equal.
 * Non-numeric parts are compared lexicographically.
 */
export function compareVersions(a: string, b: string): 1 | -1 | 0 {
  const parse = (v: string): [number, number, number] => {
    const parts = v.split('.').map((n) => parseInt(n, 10) || 0);
    return [parts[0] ?? 0, parts[1] ?? 0, parts[2] ?? 0];
  };
  const [aMaj, aMin, aPat] = parse(a);
  const [bMaj, bMin, bPat] = parse(b);
  if (aMaj !== bMaj) return aMaj > bMaj ? 1 : -1;
  if (aMin !== bMin) return aMin > bMin ? 1 : -1;
  if (aPat !== bPat) return aPat > bPat ? 1 : -1;
  return 0;
}

/** Strip a leading "v" from a version tag (e.g. "v1.2.3" → "1.2.3"). */
export function stripV(tag: string): string {
  return tag.startsWith('v') ? tag.slice(1) : tag;
}

/**
 * Given the raw tag name from a GitHub Release (e.g. "desktop-v1.3.0"),
 * extract just the semver portion.
 */
export function tagToVersion(tag: string): string {
  const match = /(\d+\.\d+\.\d+)$/.exec(tag);
  return match ? match[1] : stripV(tag);
}
