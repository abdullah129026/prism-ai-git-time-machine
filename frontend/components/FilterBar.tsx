"use client";

import { useEffect, useMemo, useRef } from "react";
import { Search, X } from "lucide-react";

import { commitMatchesFilter, usePrismStore } from "@/lib/store";

/** Timeline filters: free-text query (message, author, sha) + author
 *  dropdown. Non-matching commits dim in the scene. "/" focuses the input. */
export default function FilterBar() {
  const timeline = usePrismStore((s) => s.timeline);
  const filterQuery = usePrismStore((s) => s.filterQuery);
  const filterAuthor = usePrismStore((s) => s.filterAuthor);
  const setFilterQuery = usePrismStore((s) => s.setFilterQuery);
  const setFilterAuthor = usePrismStore((s) => s.setFilterAuthor);
  const clearFilters = usePrismStore((s) => s.clearFilters);
  const inputRef = useRef<HTMLInputElement>(null);

  const authors = useMemo(() => {
    const seen = new Set<string>();
    timeline?.nodes.forEach((n) => n.author && seen.add(n.author));
    return Array.from(seen).sort((a, b) => a.localeCompare(b));
  }, [timeline]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (
        e.key === "/" &&
        el &&
        el.tagName !== "INPUT" &&
        el.tagName !== "TEXTAREA"
      ) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const matchCount = useMemo(() => {
    if (!timeline) return 0;
    return timeline.nodes.filter((n) =>
      commitMatchesFilter(n, filterQuery, filterAuthor),
    ).length;
  }, [timeline, filterQuery, filterAuthor]);

  const active = filterQuery.trim() !== "" || filterAuthor !== null;

  return (
    <div className="absolute right-3 top-3 z-10 flex items-center gap-1.5">
      <div className="relative">
        <Search
          size={13}
          className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-ink-faint"
        />
        <input
          ref={inputRef}
          className="input-dark !w-44 py-1 pl-7 !text-xs"
          placeholder="Filter commits…"
          title="Filter by message, author, or sha prefix ( / )"
          spellCheck={false}
          value={filterQuery}
          onChange={(e) => setFilterQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") inputRef.current?.blur();
          }}
          aria-label="Filter commits"
        />
      </div>
      <select
        className="input-dark !w-auto cursor-pointer !py-1 !text-xs"
        value={filterAuthor ?? ""}
        onChange={(e) => setFilterAuthor(e.target.value || null)}
        aria-label="Filter by author"
        title="Filter by author"
      >
        <option value="">All authors</option>
        {authors.map((a) => (
          <option key={a} value={a}>
            {a.length > 24 ? `${a.slice(0, 24)}…` : a}
          </option>
        ))}
      </select>
      {active && (
        <>
          <span className="font-mono text-xs text-ink-faint">
            {matchCount} of {timeline?.nodes.length ?? 0}
          </span>
          <button
            className="btn-quiet !border-0 !px-2 !py-1"
            onClick={clearFilters}
            aria-label="Clear filters"
            title="Clear filters"
          >
            <X size={14} />
          </button>
        </>
      )}
    </div>
  );
}
