import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  flush,
  trackArticleClose,
  trackArticleOpen,
  trackFeature,
  trackRoute,
} from '../lib/analytics';
import { secondaryNavigationItemsFor } from '../lib/navigation';

describe('analytics tracker', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    flush(); // drain any leftover queue
    vi.unstubAllGlobals();
  });

  type FetchCall = [string, RequestInit];

  function calls(): FetchCall[] {
    return fetchMock.mock.calls as FetchCall[];
  }

  function lastBody(): { events: { type: string; [k: string]: unknown }[] } {
    const init = calls().at(-1)?.[1];
    return JSON.parse(init?.body as string) as {
      events: { type: string; [k: string]: unknown }[];
    };
  }

  it('posts queued events to /api/events on flush', () => {
    trackRoute('/today');
    trackFeature('ask');
    flush();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = calls()[0];
    expect(url).toBe('/api/events');
    expect(init.method).toBe('POST');
    const { events } = lastBody();
    expect(events).toEqual([
      { type: 'route', route: '/today' },
      { type: 'feature', feature: 'ask' },
    ]);
  });

  it('does not call fetch when the queue is empty', () => {
    flush();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('emits article_close with a dwell duration after open', () => {
    trackArticleOpen(42);
    trackArticleClose(42);
    flush();

    const { events } = lastBody();
    const close = events.find((e) => e.type === 'article_close');
    expect(close?.article_id).toBe(42);
    expect(typeof close?.duration_ms).toBe('number');
  });

  it('ignores a close for an article that was never opened', () => {
    trackArticleClose(999);
    flush();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('analytics navigation', () => {
  it('exposes the analytics route to admins only', () => {
    const adminRoutes = secondaryNavigationItemsFor(true).map((i) => i.to);
    const userRoutes = secondaryNavigationItemsFor(false).map((i) => i.to);
    expect(adminRoutes).toContain('/analytics');
    expect(userRoutes).not.toContain('/analytics');
  });
});
