import { useState, useEffect, useRef } from 'react';

type StreamStatus = 'connecting' | 'live' | 'error';

export function FeedsLogsPage() {
  const [lines, setLines] = useState<string[]>([]);
  const [status, setStatus] = useState<StreamStatus>('connecting');
  const [retryKey, setRetryKey] = useState(0);
  const terminalRef = useRef<HTMLPreElement | null>(null);

  useEffect(() => {
    setStatus('connecting');
    const events = new EventSource('/api/ingest/stream');

    events.onopen = () => setStatus('live');
    events.onerror = () => setStatus('error');
    events.addEventListener('reset', () => setLines([]));
    events.addEventListener('line', (event) => {
      setLines((prev) => [...prev, String((event as MessageEvent<string>).data)]);
    });

    return () => events.close();
  }, [retryKey]);

  useEffect(() => {
    const terminal = terminalRef.current;
    if (terminal) {
      terminal.scrollTop = terminal.scrollHeight;
    }
  }, [lines]);

  const isLive = status === 'live';
  const statusLabel =
    status === 'live' ? 'Live' : status === 'error' ? 'Disconnected' : 'Connecting…';

  return (
    <div className="p-4 md:p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-[22px] font-semibold tracking-tight">Logs</h2>
        <span
          className={[
            'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
            isLive
              ? 'border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400'
              : status === 'error'
                ? 'border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400'
                : 'border-border bg-muted text-muted-foreground',
          ].join(' ')}
        >
          <span
            className={[
              'h-1.5 w-1.5 rounded-full',
              isLive ? 'bg-green-500' : status === 'error' ? 'bg-red-500' : 'bg-muted-foreground',
            ].join(' ')}
          />
          {statusLabel}
        </span>
      </div>

      {status === 'error' ? (
        <div className="mb-4 flex flex-col gap-3 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300 sm:flex-row sm:items-center sm:justify-between">
          <p>Live ingest stream is unavailable or requires admin access.</p>
          <button
            type="button"
            className="inline-flex h-9 items-center justify-center rounded-md border border-red-500/40 px-3 text-sm font-medium text-red-700 transition-colors hover:bg-red-500/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 dark:text-red-300"
            onClick={() => setRetryKey((current) => current + 1)}
          >
            Retry
          </button>
        </div>
      ) : null}

      <div className="rounded-lg border border-border overflow-hidden">
        <pre
          ref={terminalRef}
          aria-live="polite"
          className={[
            'min-h-[240px] max-h-[420px] overflow-y-auto p-4',
            'font-mono text-xs leading-relaxed',
            'bg-[#0d1117] text-[#c9d1d9]',
            'dark:bg-[#0d1117] dark:text-[#c9d1d9]',
          ].join(' ')}
        >
          {lines.length ? lines.join('\n') : 'Waiting for ingest output…'}
        </pre>
      </div>
    </div>
  );
}
