import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import {
  fetchReadingDna,
  fetchRecommendationPreferences,
  saveRecommendationPreferences,
} from '../api';
import type { ReadingDna, ReadingDnaBucket, RecommendationPreferences } from '../types';

const DEFAULT_CATEGORIES = ['tech', 'science', 'business', 'world', 'ai'];

interface PageState {
  dna: ReadingDna | null;
  preferences: RecommendationPreferences | null;
  loading: boolean;
  saving: boolean;
  error: string | null;
}

export function ReadingDnaPage() {
  const [state, setState] = useState<PageState>({
    dna: null,
    preferences: null,
    loading: true,
    saving: false,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchReadingDna(), fetchRecommendationPreferences()])
      .then(([dna, preferences]) => {
        if (!cancelled) {
          setState({ dna, preferences, loading: false, saving: false, error: null });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setState((s) => ({
            ...s,
            loading: false,
            error: err instanceof Error ? err.message : 'Failed to load Reading DNA',
          }));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const categories = useMemo(() => {
    const fromStats = state.dna?.categories.map((item) => item.category).filter(Boolean) ?? [];
    return Array.from(new Set([...fromStats, ...DEFAULT_CATEGORIES])).slice(0, 8) as string[];
  }, [state.dna]);

  async function updatePreferences(next: Partial<RecommendationPreferences>) {
    if (!state.preferences) return;
    const optimistic = {
      ...state.preferences,
      ...next,
      category_weights: next.category_weights ?? state.preferences.category_weights,
    };
    setState((s) => ({ ...s, preferences: optimistic, saving: true, error: null }));
    try {
      const preferences = await saveRecommendationPreferences(next);
      const dna = await fetchReadingDna();
      setState((s) => ({ ...s, dna, preferences, saving: false }));
    } catch (err) {
      setState((s) => ({
        ...s,
        saving: false,
        error: err instanceof Error ? err.message : 'Failed to save preferences',
      }));
    }
  }

  const { dna, preferences, loading, saving, error } = state;

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center p-8">
        <Loader2 className="text-muted-foreground size-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl space-y-5 p-4 md:p-5">
      <section>
        <h2 className="text-[22px] font-semibold tracking-tight">Reading DNA</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Your recent reading mix and recommendation controls
        </p>
      </section>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <section className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <Metric label="Window" value={`${dna?.range_days ?? 30}d`} />
        <Metric label="Avg dwell" value={`${dna?.average_dwell_seconds ?? 0}s`} />
        <Metric
          label="Read"
          value={String(dna?.categories.reduce((sum, item) => sum + item.done, 0) ?? 0)}
        />
        <Metric
          label="Skipped"
          value={String(dna?.categories.reduce((sum, item) => sum + item.skipped, 0) ?? 0)}
        />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Category mix">
          <BucketBars items={dna?.categories ?? []} labelKey="category" />
        </Panel>
        <Panel title="Source mix">
          <BucketBars items={dna?.sources ?? []} labelKey="source" />
        </Panel>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Panel title="Time on app">
          <div className="flex h-40 items-end gap-2">
            {(dna?.monthly_time ?? []).map((point) => {
              const max = Math.max(...(dna?.monthly_time ?? []).map((p) => p.minutes), 1);
              return (
                <div key={point.month} className="flex h-full flex-1 flex-col justify-end gap-2">
                  <div
                    className="min-h-1 rounded-t bg-chart-2"
                    style={{ height: `${Math.max(4, (point.minutes / max) * 100)}%` }}
                    title={`${point.minutes} min`}
                  />
                  <div className="truncate text-center text-[10px] text-subtle">{point.month}</div>
                </div>
              );
            })}
            {dna?.monthly_time.length === 0 && <EmptyLine />}
          </div>
        </Panel>

        <Panel title="Active nudges">
          <div className="space-y-4">
            {categories.map((category) => {
              const value = preferences?.category_weights[category] ?? 1;
              return (
                <SliderRow
                  key={category}
                  label={category}
                  value={value}
                  onChange={(next) =>
                    void updatePreferences({
                      category_weights: {
                        ...(preferences?.category_weights ?? {}),
                        [category]: next,
                      },
                    })
                  }
                />
              );
            })}
            <SliderRow
              label="novelty"
              value={preferences?.novelty_weight ?? 1}
              onChange={(next) => void updatePreferences({ novelty_weight: next })}
            />
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {saving && <RefreshCw className="size-3 animate-spin" />}
              <span>{saving ? 'Saving and recalculating' : 'Changes save immediately'}</span>
            </div>
          </div>
        </Panel>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-md border border-border bg-surface p-3">
      <h3 className="text-sm font-medium">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function BucketBars({
  items,
  labelKey,
}: {
  items: ReadingDnaBucket[];
  labelKey: 'category' | 'source';
}) {
  if (items.length === 0) return <EmptyLine />;
  return (
    <div className="space-y-3">
      {items.slice(0, 8).map((item) => {
        const label = item[labelKey] ?? 'unknown';
        return (
          <div key={label} className="space-y-1">
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="truncate font-medium capitalize">{label}</span>
              <span className="text-muted-foreground tabular-nums">{item.percentage}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded bg-muted">
              <div className="h-full bg-chart-1" style={{ width: `${item.percentage}%` }} />
            </div>
            <div className="text-[10px] text-subtle">
              {item.done} read / {item.skipped} skipped
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SliderRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block space-y-1.5">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="font-medium capitalize">{label}</span>
        <span className="tabular-nums text-muted-foreground">{value.toFixed(1)}x</span>
      </div>
      <input
        className="w-full accent-primary"
        type="range"
        min="0"
        max="3"
        step="0.1"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

function EmptyLine() {
  return <div className="py-8 text-center text-sm text-muted-foreground">No activity yet</div>;
}
