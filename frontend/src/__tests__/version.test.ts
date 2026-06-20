import { describe, it, expect } from 'vitest';
import { compareVersions, stripV, tagToVersion } from '../lib/version';

describe('compareVersions', () => {
  it('returns 0 for equal versions', () => {
    expect(compareVersions('1.2.3', '1.2.3')).toBe(0);
  });

  it('returns 1 when major is greater', () => {
    expect(compareVersions('2.0.0', '1.9.9')).toBe(1);
  });

  it('returns -1 when major is smaller', () => {
    expect(compareVersions('1.0.0', '2.0.0')).toBe(-1);
  });

  it('compares minor when major is equal', () => {
    expect(compareVersions('1.3.0', '1.2.9')).toBe(1);
    expect(compareVersions('1.2.0', '1.3.0')).toBe(-1);
  });

  it('compares patch when major and minor are equal', () => {
    expect(compareVersions('1.2.4', '1.2.3')).toBe(1);
    expect(compareVersions('1.2.3', '1.2.4')).toBe(-1);
  });

  it('treats missing segments as 0', () => {
    expect(compareVersions('1.2.0', '1.2')).toBe(0);
  });
});

describe('stripV', () => {
  it('strips leading v', () => {
    expect(stripV('v1.2.3')).toBe('1.2.3');
  });

  it('leaves bare version unchanged', () => {
    expect(stripV('1.2.3')).toBe('1.2.3');
  });
});

describe('tagToVersion', () => {
  it('extracts semver from desktop tag', () => {
    expect(tagToVersion('desktop-v1.3.0')).toBe('1.3.0');
  });

  it('extracts semver from android tag', () => {
    expect(tagToVersion('android-v2.0.1')).toBe('2.0.1');
  });

  it('handles plain v-prefixed tag', () => {
    expect(tagToVersion('v1.2.3')).toBe('1.2.3');
  });
});
