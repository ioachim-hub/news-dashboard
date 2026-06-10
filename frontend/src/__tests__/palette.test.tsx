// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CommandPalette } from '../components/CommandPalette';
import { FocusedArticleProvider } from '../contexts/focusedArticle';
import * as api from '../api';

// Silence sonner in tests
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), {
    loading: vi.fn(() => 'toast-id'),
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

// Mock the triage mutations so the palette doesn't need React Query internals
vi.mock('../hooks/useTriageMutations', () => ({
  useTriageMutations: () => ({
    setState: vi.fn(),
    toggleStar: vi.fn(),
    sendLater: vi.fn(),
  }),
  ARTICLES_KEY: 'articles',
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <FocusedArticleProvider>{children}</FocusedArticleProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ─── CommandPalette ───────────────────────────────────────────────────────────

describe('CommandPalette — open / close', () => {
  it('renders nothing when closed', () => {
    render(
      <Wrapper>
        <CommandPalette open={false} onOpenChange={vi.fn()} />
      </Wrapper>
    );
    expect(screen.queryByPlaceholderText(/jump to a view/i)).toBeNull();
  });

  it('shows the search input when open', () => {
    render(
      <Wrapper>
        <CommandPalette open={true} onOpenChange={vi.fn()} />
      </Wrapper>
    );
    expect(screen.getByPlaceholderText(/jump to a view/i)).toBeTruthy();
  });

  it('calls onOpenChange(false) when Escape is pressed', async () => {
    const onOpenChange = vi.fn();
    render(
      <Wrapper>
        <CommandPalette open={true} onOpenChange={onOpenChange} />
      </Wrapper>
    );
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' });
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });
});

describe('CommandPalette — navigation items', () => {
  it('shows all navigation items', () => {
    render(
      <Wrapper>
        <CommandPalette open={true} onOpenChange={vi.fn()} />
      </Wrapper>
    );
    expect(screen.getByText('Today')).toBeTruthy();
    expect(screen.getByText('Later')).toBeTruthy();
    expect(screen.getByText('Starred')).toBeTruthy();
    expect(screen.getByText('Feeds')).toBeTruthy();
    expect(screen.getByText('Archive')).toBeTruthy();
  });

  it('shows "Refresh feeds now" action', () => {
    render(
      <Wrapper>
        <CommandPalette open={true} onOpenChange={vi.fn()} />
      </Wrapper>
    );
    expect(screen.getByText(/refresh feeds now/i)).toBeTruthy();
  });

  it('shows keyboard shortcuts item when onShortcuts provided', () => {
    render(
      <Wrapper>
        <CommandPalette open={true} onOpenChange={vi.fn()} onShortcuts={vi.fn()} />
      </Wrapper>
    );
    expect(screen.getByText(/keyboard shortcuts/i)).toBeTruthy();
  });
});

describe('CommandPalette — article search', () => {
  beforeEach(() => {
    vi.spyOn(api, 'searchArticles').mockResolvedValue([
      {
        id: 10,
        url: 'https://example.com/a',
        title: 'Test search result',
        source_name: 'TechCrunch',
        category: 'ai-llm',
        kind: 'rss',
        published_at: '2024-01-01T10:00:00Z',
        discovered_at: '2024-01-01T11:00:00Z',
        status: 'new',
        importance_score: 0.8,
        summary: 'A summary',
        reason: 'Why it matters',
        tags: '[]',
        read_at: null,
        saved_at: null,
        skipped_at: null,
        archived_at: null,
      },
    ]);
  });

  it('calls searchArticles after typing in the input', async () => {
    render(
      <Wrapper>
        <CommandPalette open={true} onOpenChange={vi.fn()} />
      </Wrapper>
    );
    const input = screen.getByPlaceholderText(/jump to a view/i);
    await userEvent.type(input, 'test');
    await waitFor(() => expect(api.searchArticles).toHaveBeenCalledWith('test', 6), {
      timeout: 1000,
    });
  });

  it('shows article results from the API', async () => {
    render(
      <Wrapper>
        <CommandPalette open={true} onOpenChange={vi.fn()} />
      </Wrapper>
    );
    const input = screen.getByPlaceholderText(/jump to a view/i);
    await userEvent.type(input, 'test');
    await waitFor(() => expect(screen.getByText('Test search result')).toBeTruthy(), {
      timeout: 1000,
    });
  });
});

describe('CommandPalette — ingest action', () => {
  it('calls ingestNow when "Refresh feeds now" is selected', async () => {
    const ingestSpy = vi.spyOn(api, 'ingestNow').mockResolvedValue({ inserted: 3, results: {} });
    const onOpenChange = vi.fn();
    render(
      <Wrapper>
        <CommandPalette open={true} onOpenChange={onOpenChange} />
      </Wrapper>
    );
    const refreshBtn = screen.getByText(/refresh feeds now/i);
    fireEvent.click(refreshBtn);
    await waitFor(() => expect(ingestSpy).toHaveBeenCalled());
  });
});
