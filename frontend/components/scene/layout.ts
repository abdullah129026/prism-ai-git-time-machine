/**
 * Pure layout math for the 3D scene. Kept framework-free so it can be
 * unit-tested and reused by the timeline graph, the city view, and the
 * scrubber without importing three.js.
 */
import type { FileChurn, TimelineEdge, TimelineNode } from "@/lib/api";

export interface PlacedNode {
  sha: string;
  x: number;
  y: number;
  z: number;
  radius: number;
  t: number; // epoch ms
  churn: number; // additions + deletions
}

export interface TimelineLayout {
  nodes: PlacedNode[];
  bySha: Map<string, PlacedNode>;
  /** Pairs of [x, y, z] endpoints for parent→child edge segments. */
  edges: Array<[[number, number, number], [number, number, number]]>;
  width: number;
  /** SHAs ordered oldest → newest. */
  orderedShas: string[];
  tMin: number;
  tMax: number;
}

/** Deterministic pseudo-random in [0, 1) from a string + seed. */
function hash01(s: string, seed: number): number {
  let h = seed >>> 0;
  for (let i = 0; i < s.length; i++) {
    h = Math.imul(h ^ s.charCodeAt(i), 2654435761);
  }
  return ((h >>> 0) % 1000) / 1000;
}

/** Node radius grows with the square root of churn, capped. */
export function nodeRadius(churn: number): number {
  return 0.24 + Math.min(0.85, Math.sqrt(Math.max(0, churn)) / 16);
}

/**
 * Lay commits on a time axis: x = time (oldest left), z = a deterministic
 * jitter so dense bursts don't perfectly overlap, y = 0 plane.
 */
export function layoutTimeline(
  timelineNodes: TimelineNode[],
  timelineEdges: TimelineEdge[],
): TimelineLayout {
  const parsed = timelineNodes.map((n) => ({
    n,
    t: Date.parse(n.committed_at) || 0,
  }));
  const sorted = [...parsed].sort((a, b) => a.t - b.t);
  const tMin = sorted.length > 0 ? sorted[0].t : 0;
  const tMax = sorted.length > 0 ? sorted[sorted.length - 1].t : 0;
  const span = Math.max(1, tMax - tMin);
  const width = Math.max(48, sorted.length * 0.55);

  const nodes: PlacedNode[] = sorted.map(({ n, t }) => {
    const churn = n.additions + n.deletions;
    return {
      sha: n.sha,
      x: ((t - tMin) / span) * width - width / 2,
      y: 0,
      z: (hash01(n.sha, 7) - 0.5) * 7,
      radius: nodeRadius(churn),
      t,
      churn,
    };
  });

  const bySha = new Map(nodes.map((p) => [p.sha, p]));
  const edges: TimelineLayout["edges"] = [];
  for (const e of timelineEdges) {
    const a = bySha.get(e.source);
    const b = bySha.get(e.target);
    if (a && b) {
      edges.push([
        [a.x, a.y, a.z],
        [b.x, b.y, b.z],
      ]);
    }
  }

  return {
    nodes,
    bySha,
    edges,
    width,
    orderedShas: nodes.map((p) => p.sha),
    tMin,
    tMax,
  };
}

export interface Building {
  path: string;
  x: number;
  z: number;
  w: number;
  h: number;
  d: number;
  churn: number;
  commits: number;
  /** 0..1 monochrome intensity by churn rank (log scale). */
  shade: number;
}

export interface CityLayout {
  buildings: Building[];
  cols: number;
  rows: number;
  cell: number;
}

/**
 * File "buildings": height = log(churn), footprint grows with the number of
 * commits touching the file. Files arrive pre-sorted by churn (top 50).
 */
export function layoutCity(files: FileChurn[]): CityLayout {
  const n = files.length;
  const cols = Math.max(1, Math.ceil(Math.sqrt(n)));
  const rows = Math.max(1, Math.ceil(n / cols));
  const cell = 3.2;
  const maxChurn = Math.max(
    1,
    ...files.map((f) => f.additions + f.deletions),
  );
  const logMax = Math.log10(1 + maxChurn);

  const buildings = files.map((f, i) => {
    const churn = f.additions + f.deletions;
    const frac = logMax > 0 ? Math.log10(1 + churn) / logMax : 0;
    const col = i % cols;
    const row = Math.floor(i / cols);
    const footprint = 1.15 + Math.min(1.15, f.commits / 14);
    return {
      path: f.path,
      x: (col - (cols - 1) / 2) * cell,
      z: (row - (rows - 1) / 2) * cell,
      w: footprint,
      h: 0.6 + frac * 9,
      d: footprint,
      churn,
      commits: f.commits,
      shade: frac,
    };
  });

  return { buildings, cols, rows, cell };
}

/** "Oct 3, 2026" style label for axis ticks and the scrubber. */
export function formatShortDate(t: number): string {
  const d = new Date(t);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
}
