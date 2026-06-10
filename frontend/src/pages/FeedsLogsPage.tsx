import { useState, useEffect, useRef } from 'react';

export function FeedsLogsPage() {
  const [lines, setLines] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const terminalRef = useRef<HTMLPreElement | null>(null);

  useEffect(() => {
    const events = new EventSource('/api/ingest/stream');

    events.onopen = () => setConnected(true);
    events.onerror = () => setConnected(false);
    events.addEventListener('reset', () => setLines([]));
    events.addEventListener('line', (event) => {
      setLines((prev) => [...prev, String((event as MessageEvent<string>).data)]);
    });

    return () => events.close();
  }, []);

  useEffect(() => {
    const terminal = terminalRef.current;
    if (terminal) {
      terminal.scrollTop = terminal.scrollHeight;
    }
  }, [lines]);

  return (
    <div className="p-4 md:p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-[22px] font-semibold tracking-tight">Logs</h2>
        <span
          className={[
            'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
            connected
              ? 'border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400'
              : 'border-border bg-muted text-muted-foreground',
          ].join(' ')}
        >
          <span
            className={[
              'h-1.5 w-1.5 rounded-full',
              connected ? 'bg-green-500' : 'bg-muted-foreground',
            ].join(' ')}
          />
          {connected ? 'Live' : 'Connecting…'}
        </span>
      </div>

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
