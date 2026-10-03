"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo } from "react";

import type { TimelineNode } from "@/lib/api";
import type { TimelineLayout } from "./scene/layout";

interface ScrubberProps {
  layout: TimelineLayout;
  nodes: TimelineNode[];
  selectedSha: string | null;
  onSelect: (sha: string | null) => void;
}

/** Bottom time scrubber: drag through history, step with buttons. */
export default function Scrubber({
  layout,
  nodes,
  selectedSha,
  onSelect,
}: ScrubberProps) {
  const metaBySha = useMemo(
    () => new Map(nodes.map((n) => [n.sha, n])),
    [nodes],
  );

  const count = layout.orderedShas.length;
  const idx = selectedSha
    ? Math.max(0, layout.orderedShas.indexOf(selectedSha))
    : count - 1;
  const meta = selectedSha ? metaBySha.get(selectedSha) : undefined;

  const step = (delta: number) => {
    if (count === 0) return;
    const next = Math.min(count - 1, Math.max(0, idx + delta));
    onSelect(layout.orderedShas[next]);
  };

  if (count === 0) return null;

  return (
    <div className="absolute inset-x-0 bottom-0 z-10 border-t hairline bg-surface px-4 py-2.5">
      <div className="flex items-center gap-3">
        <button
          className="btn-quiet shrink-0 !px-2"
          onClick={() => step(-1)}
          aria-label="Previous commit"
          disabled={idx <= 0}
        >
          <ChevronLeft size={14} />
        </button>
        <input
          type="range"
          min={0}
          max={count - 1}
          value={idx}
          onChange={(e) => onSelect(layout.orderedShas[Number(e.target.value)])}
          className="prism-range min-w-0 flex-1"
          aria-label="Scrub commit history"
        />
        <button
          className="btn-quiet shrink-0 !px-2"
          onClick={() => step(1)}
          aria-label="Next commit"
          disabled={idx >= count - 1}
        >
          <ChevronRight size={14} />
        </button>
        <div className="hidden w-80 shrink-0 truncate text-xs md:block">
          {meta ? (
            <>
              <span className="font-mono text-accent">
                {meta.sha.slice(0, 7)}
              </span>{" "}
              <span className="text-ink-dim">
                {meta.message.split("\n")[0]}
              </span>
            </>
          ) : (
            <span className="text-ink-faint">
              Drag to scrub through history
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
