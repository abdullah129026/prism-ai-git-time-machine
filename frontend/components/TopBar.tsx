"use client";

import { Command, GitBranch, Loader2, Search } from "lucide-react";
import { useState } from "react";
import { usePrismStore } from "@/lib/store";

/** Top bar: wordmark, repo URL input + Explore, command palette trigger. */
export default function TopBar() {
  const repoUrl = usePrismStore((s) => s.repoUrl);
  const setRepoUrl = usePrismStore((s) => s.setRepoUrl);
  const exploreRepo = usePrismStore((s) => s.exploreRepo);
  const ingestStatus = usePrismStore((s) => s.ingestStatus);
  const ingestError = usePrismStore((s) => s.ingestError);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const ingesting = ingestStatus === "ingesting";

  const submit = () => {
    void exploreRepo(repoUrl);
  };

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b hairline bg-surface px-3">
      <div className="flex items-center gap-2">
        <GitBranch size={16} className="text-accent" />
        <span className="font-mono text-sm font-semibold tracking-wide">PRISM</span>
      </div>

      <form
        className="relative flex max-w-2xl flex-1 items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div className="relative flex-1">
          <Search
            size={14}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint"
          />
          <input
            className="input-dark pl-8"
            placeholder="Paste a git repo URL to explore…"
            spellCheck={false}
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            aria-label="Repository URL"
          />
        </div>
        <button
          type="submit"
          className="btn-accent shrink-0"
          disabled={ingesting || !repoUrl.trim()}
        >
          {ingesting && <Loader2 size={14} className="animate-spin" />}
          {ingesting ? "Parsing…" : "Explore"}
        </button>
      </form>

      {ingestStatus === "error" && ingestError && (
        <p className="max-w-xs truncate text-xs text-danger" title={ingestError}>
          {ingestError}
        </p>
      )}

      <div className="ml-auto">
        <button
          className="btn-quiet"
          onClick={() => setPaletteOpen((v) => !v)}
          aria-label="Command palette"
        >
          <Command size={14} />
          <span className="kbd">⌘K</span>
        </button>
        {paletteOpen && (
          <div className="absolute right-3 top-14 z-10 w-72 rounded border hairline bg-elevated p-2 shadow-none">
            <p className="px-2 py-1 text-xs text-ink-faint">Keyboard</p>
            <ul className="space-y-1 text-sm">
              <li className="flex justify-between rounded px-2 py-1 hover:bg-surface">
                <span>Command palette</span>
                <span className="kbd">⌘K</span>
              </li>
              <li className="flex justify-between rounded px-2 py-1 hover:bg-surface">
                <span>Select commit</span>
                <span className="kbd">↑ ↓</span>
              </li>
              <li className="flex justify-between rounded px-2 py-1 hover:bg-surface">
                <span>Deselect</span>
                <span className="kbd">Esc</span>
              </li>
            </ul>
          </div>
        )}
      </div>
    </header>
  );
}
