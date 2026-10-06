"use client";

import { FolderGit2, Loader2 } from "lucide-react";
import { usePrismStore } from "@/lib/store";

/** Actionable empty state: explore a repo URL, or prefill the sample repo. */
export default function EmptyState() {
  const repoUrl = usePrismStore((s) => s.repoUrl);
  const setRepoUrl = usePrismStore((s) => s.setRepoUrl);
  const exploreRepo = usePrismStore((s) => s.exploreRepo);
  const ingestStatus = usePrismStore((s) => s.ingestStatus);
  const ingestError = usePrismStore((s) => s.ingestError);
  const ingestProgress = usePrismStore((s) => s.ingestProgress);

  const ingesting = ingestStatus === "ingesting";

  const loadSample = () =>
    setRepoUrl("https://github.com/abdullah129026/prism-ai-git-time-machine");

  const submit = () => {
    void exploreRepo(repoUrl);
  };

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
      <FolderGit2 size={28} className="text-ink-faint" />
      <div>
        <h1 className="text-lg font-medium">Explore a repository's history</h1>
        <p className="mt-1 max-w-sm text-sm text-ink-dim">
          Paste a git URL. PRISM clones it, parses every commit, and renders
          the history as a 3D timeline — select any commit to inspect its
          intent.
        </p>
      </div>
      <div className="flex w-full max-w-md gap-2">
        <input
          className="input-dark"
          placeholder="https://github.com/org/repo"
          spellCheck={false}
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          aria-label="Repository URL"
        />
        <button
          className="btn-quiet shrink-0"
          onClick={loadSample}
          disabled={ingesting}
        >
          Try sample
        </button>
      </div>
      <button
        className="btn-accent"
        onClick={submit}
        disabled={ingesting || !repoUrl.trim()}
      >
        {ingesting && <Loader2 size={14} className="animate-spin" />}
        {ingesting ? "Cloning and parsing…" : "Explore repository"}
      </button>
      {ingesting && (
        <p className="font-mono text-xs text-ink-dim">
          {ingestProgress
            ? `${ingestProgress.stage} — ${ingestProgress.commits} commits parsed`
            : "Starting…"}
        </p>
      )}
      {ingestStatus === "error" && ingestError && (
        <p className="max-w-md text-xs text-danger">{ingestError}</p>
      )}
      <p className="font-mono text-xs text-ink-faint">
        3D timeline: click a node, scrub the axis, or use ↑ ↓
      </p>
    </div>
  );
}
