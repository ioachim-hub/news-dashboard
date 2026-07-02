import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { EntityType, KnowledgeGraphEdge, KnowledgeGraphResponse } from '@/types';
import { forceLayout } from '@/lib/forceLayout';
import { cn } from '@/lib/utils';

const CANVAS_W = 800;
const CANVAS_H = 600;

const TYPE_COLORS: Record<EntityType, string> = {
  person: 'var(--color-chart-1)',
  org: 'var(--color-chart-2)',
  product: 'var(--color-chart-3)',
  place: 'var(--color-chart-4)',
};

function nodeRadius(count: number): number {
  return 6 + 3 * Math.sqrt(count);
}

function isIncident(edge: KnowledgeGraphEdge, nodeId: string): boolean {
  return edge.source === nodeId || edge.target === nodeId;
}

interface KnowledgeGraphProps {
  graph: KnowledgeGraphResponse;
}

export function KnowledgeGraph({ graph }: KnowledgeGraphProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const layout = useMemo(
    () => forceLayout(graph.nodes, graph.edges, CANVAS_W, CANVAS_H),
    [graph.nodes, graph.edges]
  );

  const selected = useMemo(
    () => graph.nodes.find((n) => n.id === selectedId) ?? null,
    [graph.nodes, selectedId]
  );

  const selectedArticles = useMemo(() => {
    if (!selected) return [];
    const wanted = new Set(selected.article_ids);
    return graph.articles.filter((a) => wanted.has(a.id));
  }, [graph.articles, selected]);

  if (graph.nodes.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-muted-foreground">
        {graph.pending_count > 0
          ? `No entities yet — extraction is still running for ${graph.pending_count} article${
              graph.pending_count !== 1 ? 's' : ''
            }.`
          : 'No entities yet — the graph fills in as articles are analyzed.'}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <svg viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`} className="h-auto w-full" role="img">
        <title>Knowledge graph of entities in recent news</title>
        {graph.edges.map((edge) => {
          const a = layout.get(edge.source);
          const b = layout.get(edge.target);
          if (!a || !b) return null;
          const dimmed = selectedId !== null && !isIncident(edge, selectedId);
          return (
            <line
              key={`${edge.source}--${edge.target}`}
              data-testid="kg-edge"
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              strokeWidth={Math.min(1 + edge.weight, 6)}
              className={cn('stroke-primary/30', dimmed && 'stroke-primary/10')}
            />
          );
        })}
        {graph.nodes.map((node) => {
          const p = layout.get(node.id);
          if (!p) return null;
          const dimmed = selectedId !== null && selectedId !== node.id;
          return (
            <g key={node.id}>
              <circle
                data-testid="kg-node"
                data-entity={node.id}
                cx={p.x}
                cy={p.y}
                r={nodeRadius(node.count)}
                fill={TYPE_COLORS[node.type]}
                fillOpacity={dimmed ? 0.3 : 0.85}
                className="cursor-pointer stroke-background stroke-[1.5] transition-all"
                onClick={() => setSelectedId((prev) => (prev === node.id ? null : node.id))}
              >
                <title>{`${node.name} — ${node.count} article${node.count !== 1 ? 's' : ''}`}</title>
              </circle>
              <text
                x={p.x}
                y={p.y - nodeRadius(node.count) - 4}
                textAnchor="middle"
                className={cn(
                  'pointer-events-none select-none fill-foreground text-[11px] font-medium',
                  dimmed && 'opacity-30'
                )}
              >
                {node.name}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {(Object.keys(TYPE_COLORS) as EntityType[]).map((type) => (
          <span key={type} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span
              className="size-2.5 rounded-full"
              style={{ backgroundColor: TYPE_COLORS[type] }}
            />
            {type}
          </span>
        ))}
      </div>

      {selected && (
        <div className="rounded-xl border border-border bg-surface-2 p-4">
          <h3 className="text-sm font-semibold">
            {selected.name}{' '}
            <span className="font-normal text-muted-foreground">
              · {selected.type} · {selected.count} article{selected.count !== 1 ? 's' : ''}
            </span>
          </h3>
          <ul className="mt-2 grid gap-1.5">
            {selectedArticles.map((article) => (
              <li key={article.id}>
                <Link
                  to={`/a/${article.id}`}
                  className="text-xs text-foreground hover:text-primary hover:underline"
                >
                  {article.title}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
