"use client";

import { useMemo } from "react";

import type { TimelineNode } from "@/lib/api";
import { commitMatchesFilter, usePrismStore } from "@/lib/store";
import { formatShortDate } from "./scene/layout";

interface Timeline2DProps {
  nodes: TimelineNode[];
  selectedSha: string | null;
  onSelect: (sha: string | null) => void;
}

const DX = 30;
const LANE_H = 32;
const PAD_X = 40;
const PAD_Y = 34;
const NODE_R = 5.5;
const NODE_FILL = "#565d66";
const EDGE_COLOR = "rgba(255,255,255,0.14)";
const ACCENT = "#5E6AD2";

interface Placed {
  x: number;
  y: number;
}

/**
 * Greedy lane assignment, newest-first: a node takes the lane of the
 * first tip matching its sha, otherwise opens a new lane; its parents
 * become the new tips. # ponytail: O(n^2) worst case on lane scan,
 * fine under a few thousand nodes; bucket tips if it ever grows.
 */
function layout2D(nodes: TimelineNode[]) {
  const ordered = [...nodes].sort(
    (a, b) => Date.parse(a.committed_at) - Date.parse(b.committed_at),
  );
  const lanes: (string | null)[] = [];
  const laneOf = new Map<string, number>();

  for (const n of [...ordered].reverse()) {
    let lane = lanes.findIndex((tip) => tip === n.sha);
    if (lane === -1) {
      lane = lanes.length;
      lanes.push(n.sha);
    }
    laneOf.set(n.sha, lane);
    lanes[lane] = n.parents[0] ?? null;
    for (const p of n.parents) {
      if (!lanes.includes(p)) lanes.push(p);
    }
  }

  const pos = new Map<string, Placed>();
  ordered.forEach((n, i) =>
    pos.set(n.sha, {
      x: PAD_X + i * DX,
      y: PAD_Y + (laneOf.get(n.sha) ?? 0) * LANE_H,
    }),
  );

  const edges: { x1: number; y1: number; x2: number; y2: number }[] = [];
  for (const n of ordered) {
    const a = pos.get(n.sha);
    if (!a) continue;
    for (const p of n.parents) {
      const b = pos.get(p);
      if (b) edges.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y });
    }
  }

  const times = ordered.map((n) => Date.parse(n.committed_at));
  const tMin = Math.min(...times);
  const tMax = Math.max(...times);
  const width = PAD_X * 2 + Math.max(0, ordered.length - 1) * DX;
  const height = PAD_Y * 2 + Math.max(0, lanes.length - 1) * LANE_H;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({
    x: PAD_X + f * Math.max(0, ordered.length - 1) * DX,
    label: formatShortDate(tMin + f * Math.max(1, tMax - tMin)),
  }));

  return { ordered, pos, edges, ticks, width, height };
}

/**
 * 2D fallback for the commit timeline: same nodes, edges, selection,
 * and filter dimming as the 3D scene, rendered as plain SVG. Used on
 * mobile / touch devices and wherever WebGL is unavailable.
 */
export default function Timeline2D({
  nodes,
  selectedSha,
  onSelect,
}: Timeline2DProps) {
  const filterQuery = usePrismStore((s) => s.filterQuery);
  const filterAuthor = usePrismStore((s) => s.filterAuthor);

  const { ordered, pos, edges, ticks, width, height } = useMemo(
    () => layout2D(nodes),
    [nodes],
  );

  const matches = useMemo(() => {
    const map = new Map<string, boolean>();
    for (const n of ordered) {
      map.set(n.sha, commitMatchesFilter(n, filterQuery, filterAuthor));
    }
    return map;
  }, [ordered, filterQuery, filterAuthor]);

  return (
    <div className="h-full overflow-auto bg-canvas" data-testid="timeline-2d">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label="Commit history, 2D view"
      >
        {edges.map((e, i) => (
          <line
            key={i}
            x1={e.x1}
            y1={e.y1}
            x2={e.x2}
            y2={e.y2}
            stroke={EDGE_COLOR}
            strokeWidth={1.5}
          />
        ))}
        {ticks.map((t, i) => (
          <text
            key={i}
            x={t.x}
            y={height - 6}
            textAnchor="middle"
            fill="#565d66"
            fontSize={10}
            fontFamily="JetBrains Mono, monospace"
          >
            {t.label}
          </text>
        ))}
        {ordered.map((n) => {
          const p = pos.get(n.sha);
          if (!p) return null;
          const selected = n.sha === selectedSha;
          const dimmed = !matches.get(n.sha);
          return (
            <g
              key={n.sha}
              transform={`translate(${p.x}, ${p.y})`}
              opacity={dimmed ? 0.18 : 1}
              onClick={() => onSelect(selected ? null : n.sha)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(selected ? null : n.sha);
                }
              }}
              tabIndex={0}
              role="button"
              aria-label={`Commit ${n.sha.slice(0, 7)}: ${n.message.split("\n")[0]}`}
              style={{ cursor: "pointer" }}
            >
              <title>
                {n.message.split("\n")[0] || "(no message)"}
                {"\n"}
                {n.author} · +{n.additions}/-{n.deletions}
              </title>
              {selected && (
                <circle
                  r={NODE_R + 4}
                  fill="none"
                  stroke={ACCENT}
                  strokeWidth={2}
                />
              )}
              <circle r={NODE_R} fill={NODE_FILL} />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
