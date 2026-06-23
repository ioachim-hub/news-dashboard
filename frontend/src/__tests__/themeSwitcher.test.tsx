// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ThemeSwitcher } from '../components/ThemeSwitcher';

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('ThemeSwitcher', () => {
  it('renders one toggle button per theme option', () => {
    render(<ThemeSwitcher />);
    expect(screen.getByLabelText('Light')).toBeTruthy();
    expect(screen.getByLabelText('System')).toBeTruthy();
    expect(screen.getByLabelText('Dark')).toBeTruthy();
  });

  it('marks the active theme as pressed and switches on click', () => {
    render(<ThemeSwitcher />);
    const dark = screen.getByLabelText('Dark');
    expect(dark.getAttribute('aria-pressed')).toBe('false');

    fireEvent.click(dark);

    expect(dark.getAttribute('aria-pressed')).toBe('true');
    expect(localStorage.getItem('theme')).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });
});
