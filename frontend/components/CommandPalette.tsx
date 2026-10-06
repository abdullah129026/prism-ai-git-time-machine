"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Building2,
  Command,
  GitCommitHorizontal,
  Search,
  XCircle,
} from "lucide-react";

import { commitMatchesFilter, usePrismStore } from "@/lib/store";

type Item =
  | { kind: "commit"; sha: string; title: string; sub: string }
  | {
      kind: "action";
      title: string;
      sub: string;
      icon: React.ReactNode;
      run: () => void;
    };

/**
 * ⌘K palette: fuzzy-ish search over the loaded timeline commits
 * (message, author, sha prefix) plus a few view actions. Self-contained:
 * owns the trigger button, the global hotkey, and the modal.
 */
export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const timeline = usePrismStore((s) => s.timeline);
  const selectCommit = usePrismStore((s) => s.selectCommit);
  const setViewMode = usePrismStore((s) => s.setViewMode);

  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Global toggle: ⌘K / Ctrl+K.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open ]);

  const items: Item[] = useMemo(() => {
    const actions: Item[] = [
      {
        kind: "action",
        title: "Switch to timeline view",
        sub: "view",
        icon: <GitCommitHorizontal size={14} className="text-ink-faint" />,
        run: () => setViewMode("timeline"),
      },
      {
        kind: "action",
        title: "Switch to city view",
        sub: "view",
        icon: <Building2 size={14} className="text-ink-faint" />,
        run: () => setViewMode("city"),
      },
      {
        kind: "action",
        title: "Clear commit selection",
        sub: "selection",
        icon: <XCircle size={14} className="text-ink-faint" />,
        run: () => selectCommit(null),
      },
    ];
    const q = query.trim().toLowerCase();
    const matchedActions = q
      ? actions.filter((a) => a.title.toLowerCase().includes(q))
      : actions;
    const commits: Item[] = [];
    if (timeline) {
      // # ponytail: cap at 12 hits; the list is a launcher, not a report.
      for (const n of timeline.nodes) {
        if (!q || commitMatchesFilter(n, q, null)) {
          commits.push({
            kind: "commit",
            sha: n.sha,
            title: n.message.split("\n")[0] || "(no message)",
            sub: `${n.sha.slice(0, 7)} · ${n.author}`,
          });
          if (commits.length >= 12) break;
        }
      }
    }
    return [...commits, ...matchedActions];
  }, [query, timeline, selectCommit, setViewMode]);

  useEffect(() => {
    setActive(0);
  }, [items.length]);

  const choose = (item: Item | undefined) => {
    if (!item) return;
    if (item.kind === "commit") selectCommit(item.sha);
    else item.run();
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(items.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(items[active]);
    }
  };

  // Capture-phase Escape: close without deselecting the commit behind
  // (the timeline's own Escape handler runs on bubble and never sees it).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open ]);

  useEffect(() => {
    listRef.current
      ?.querySelector(`[data-idx="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active]);

  return (
    <>
      <button
        className="btn-quiet"
        onClick={() => setOpen(true)}
        aria-label="Command palette"
      >
        <Command size={14} />
        <span className="kbd">⌘K</span>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 pt-[15vh]"
          onClick={() => setOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Command palette"
          data-command-palette
        >
          <div
            className="w-full max-w-lg overflow-hidden rounded border hairline bg-elevated"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 border-b hairline px-3">
              <Search size={14} className="shrink-0 text-ink-faint" />
              <input
                ref={inputRef}
                className="w-full bg-transparent py-3 text-sm text-ink placeholder:text-ink-faint focus:outline-none"
                placeholder="Search commits, or type an action…"
                spellCheck={false}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                aria-label="Search commits and actions"
              />
            </div>
            <ul
              ref={listRef}
              className="max-h-80 overflow-y-auto p-1.5"
              role="listbox"
            >
              {items.length === 0 && (
                <li className="px-3 py-6 text-center text-sm text-ink-faint">
                  No commits or actions match.
                </li>
              )}
              {items.map((item, i) => (
                <li key={item.kind === "commit" ? item.sha : item.title}>
                  <button
                    data-idx={i}
                    role="option"
                    aria-selected={i === active}
                    className={`flex w-full items-center gap-2.5 rounded px-2.5 py-2 text-left ${
                      i === active ? "bg-surface" : ""
                    }`}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => choose(item)}
                  >
                    {item.kind === "commit" ? (
                      <span className="shrink-0 font-mono text-xs text-accent">
                        {item.sub.split(" · ")[0]}
                      </span>
                    ) : (
                      item.icon
                    )}
                    <span className="min-w-0">
                      <span className="block truncate text-sm text-ink">
                        {item.title}
                      </span>
                      <span className="block truncate text-xs text-ink-faint">
                        {item.kind === "commit"
                          ? item.sub.split(" · ").slice(1).join(" · ")
                          : item.sub}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex items-center gap-3 border-t hairline px-3 py-2 text-xs text-ink-faint">
              <span>
                <span className="kbd">↑↓</span> navigate
              </span>
              <span>
                <span className="kbd">↵</span> open
              </span>
              <span>
                <span className="kbd">Esc</span> close
              </span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
