import { describe, it, expect } from 'vitest';
import { forceLayout } from '../lib/forceLayout';

const W = 800;
const H = 600;

const NODES = Array.from({ length: 8 }, (_, i) => ({ id: `n${i}` }));
const EDGES = [
  { source: 'n0', target: 'n1', weight: 3 },
  { source: 'n1', target: 'n2', weight: 1 },
  { source: 'n3', target: 'n4', weight: 2 },
];

describe('forceLayout', () => {
  it('returns an empty map for no nodes', () => {
    expect(forceLayout([], [], W, H).size).toBe(0);
  });

  it('positions every node inside the viewport without NaN', () => {
    const layout = forceLayout(NODES, EDGES, W, H);
    expect(layout.size).toBe(NODES.length);
    for (const { x, y } of layout.values()) {
      expect(Number.isFinite(x)).toBe(true);
      expect(Number.isFinite(y)).toBe(true);
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(W);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(H);
    }
  });

  it('is deterministic for the same input', () => {
    const a = forceLayout(NODES, EDGES, W, H);
    const b = forceLayout(NODES, EDGES, W, H);
    expect([...a.entries()]).toEqual([...b.entries()]);
  });

  it('pulls connected nodes closer than the average unconnected pair', () => {
    const layout = forceLayout(NODES, EDGES, W, H);
    const dist = (a: string, b: string) => {
      const pa = layout.get(a)!;
      const pb = layout.get(b)!;
      return Math.hypot(pa.x - pb.x, pa.y - pb.y);
    };
    const connected = EDGES.map((e) => dist(e.source, e.target));
    const connectedSet = new Set(EDGES.map((e) => [e.source, e.target].sort().join('|')));
    const unconnected: number[] = [];
    for (let i = 0; i < NODES.length; i++) {
      for (let j = i + 1; j < NODES.length; j++) {
        const key = [NODES[i].id, NODES[j].id].sort().join('|');
        if (!connectedSet.has(key)) unconnected.push(dist(NODES[i].id, NODES[j].id));
      }
    }
    const mean = (xs: number[]) => xs.reduce((s, v) => s + v, 0) / xs.length;
    expect(mean(connected)).toBeLessThan(mean(unconnected));
  });

  it('ignores edges that reference unknown nodes', () => {
    const layout = forceLayout(
      [{ id: 'a' }, { id: 'b' }],
      [{ source: 'a', target: 'ghost', weight: 1 }],
      W,
      H
    );
    expect(layout.size).toBe(2);
    for (const { x, y } of layout.values()) {
      expect(Number.isFinite(x)).toBe(true);
      expect(Number.isFinite(y)).toBe(true);
    }
  });
});
