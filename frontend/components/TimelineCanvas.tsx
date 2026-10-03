"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo } from "react";
import {
  Building2,
  GitCommitHorizontal,
  Loader2,
  RotateCcw,
} from "lucide-react";

import { usePrismStore } from "@/lib/store";
import EmptyState from "./EmptyState";
import { layoutTimeline } from "./scene/layout";

/** The R3F canvas is client-only — three.js needs the DOM. */
const Scene3D = dynamic(() => import("./Scene3D"), {
  ssr: false,
  loading: () => <SceneFallback label="Loading 3D scene…" />,
});

function SceneFallback({ label }: { label: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3">
      <Loader2 size={20} className="animate-spin text-ink-faint" />
      <p className="text-sm text-ink-dim">{label}</p>
    </div>
  );
}

/** Timeline / City view toggle, floating over the scene. */
function ViewToolbar() {
  const viewMode = usePrismStore((s) => s.viewMode);
  const setViewMode = usePrismStore((s) => s.setViewMode);
  const commitCount = usePrismStore((s) => s.timeline?.nodes.length ?? 0);

  const btn = (active: boolean) =>
    active
      ? "btn-accent !border-0 !px-2.5 !py-1 !text-xs"
      : "btn-quiet !border-0 !px-2.5 !py-1 !text-xs";

  return (
    <div className="absolute left-3 top-3 z-10 flex items-center gap-1 rounded border hairline bg-surface p-1">
      <button
        className={btn(viewMode === "timeline")}
        onClick={() => setViewMode("timeline")}
      >
        <GitCommitHorizontal size={14} />
        Timeline
      </button>
      <button
        className={btn(viewMode === "city")}
        onClick={() => setViewMode("city")}
      >
        <Building2 size={14} />
        City
      </button>
      <span className="px-2 font-mono text-xs text-ink-faint">
        {commitCount} commits
      </span>
    </div>
  );
}

/**
 * Timeline area: empty state → loading → error → the 3D explorer
 * (commit nodes on a time axis, or file-churn buildings) with a
 * scrubber, view toggle, and keyboard navigation.
 */
export default function TimelineCanvas() {
  const repoId = usePrismStore((s) => s.repoId);
  const timeline = usePrismStore((s) => s.timeline);
  const timelineStatus = usePrismStore((s) => s.timelineStatus);
  const timelineError = usePrismStore((s) => s.timelineError);
  const loadTimeline = usePrismStore((s) => s.loadTimeline);
  const viewMode = usePrismStore((s) => s.viewMode);
  const selectedCommit = usePrismStore((s) => s.selectedCommit);
  const selectCommit = usePrismStore((s) => s.selectCommit);

  useEffect(() => {
    if (repoId) void loadTimeline(repoId);
  }, [repoId, loadTimeline]);

  // Keyboard: ↑ ↓ ← → move between commits, Esc clears the selection.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) return;
      if (!timeline || timelineStatus !== "ready") return;
      if (e.key === "Escape") {
        selectCommit(null);
        return;
      }
      if (
        e.key !== "ArrowUp" &&
        e.key !== "ArrowDown" &&
        e.key !== "ArrowLeft" &&
        e.key !== "ArrowRight"
      ) {
        return;
      }
      e.preventDefault();
      const ordered = [...timeline.nodes]
        .sort(
          (a, b) =>
            Date.parse(a.committed_at) - Date.parse(b.committed_at),
        )
        .map((n) => n.sha);
      if (ordered.length === 0) return;
      const idx = selectedCommit ? ordered.indexOf(selectedCommit) : -1;
      const next =
        e.key === "ArrowUp" || e.key === "ArrowLeft"
          ? Math.max(0, idx <= 0 ? 0 : idx - 1)
          : Math.min(ordered.length - 1, idx + 1);
      selectCommit(ordered[next]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [timeline, timelineStatus, selectedCommit, selectCommit]);

  const layout = useMemo(
    () =>
      timeline ? layoutTimeline(timeline.nodes, timeline.edges) : null,
    [timeline],
  );

  if (!repoId) {
    return (
      <main className="relative flex-1 bg-canvas">
        <EmptyState />
      </main>
    );
  }

  return (
    <main className="relative min-w-0 flex-1 overflow-hidden bg-canvas">
      {(timelineStatus === "loading" || timelineStatus === "idle") && (
        <SceneFallback label="Loading timeline…" />
      )}

      {timelineStatus === "error" && (
        <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
          <p className="text-sm text-ink">Could not load the timeline.</p>
          {timelineError && (
            <p className="max-w-md font-mono text-xs text-danger">
              {timelineError}
            </p>
          )}
          <button
            className="btn-quiet"
            onClick={() => repoId && loadTimeline(repoId)}
          >
            <RotateCcw size={14} />
            Retry
          </button>
        </div>
      )}

      {timelineStatus === "ready" && timeline && layout && (
        <>
          {timeline.nodes.length === 0 ? (
            <div className="flex h-full items-center justify-center p-8">
              <p className="text-sm text-ink-dim">
                No commits were parsed for this repo.
              </p>
            </div>
          ) : (
            <>
              <ViewToolbar />
              <Scene3D
                layout={layout}
                timeline={timeline}
                viewMode={viewMode}
                selectedSha={selectedCommit}
                onSelect={selectCommit}
              />
            </>
          )}
        </>
      )}
    </main>
  );
}
