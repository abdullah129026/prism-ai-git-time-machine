"use client";

import { useState } from "react";
import { Loader2, Users } from "lucide-react";

import {
  ApiError,
  fetchOwnership,
  type OwnershipResponse,
} from "@/lib/api";
import { usePrismStore } from "@/lib/store";

type Status = "idle" | "loading" | "ready" | "error";

/** Ownership: who understands this code — ranked by substantive, recent,
 *  well-understood changes rather than git blame. Lives at the bottom of
 *  the inspector, under conflict prediction. */
export default function OwnershipView() {
  const repoId = usePrismStore((s) => s.repoId);

  const [path, setPath] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<OwnershipResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!repoId) return null;

  const run = () => {
    setStatus("loading");
    setError(null);
    fetchOwnership(repoId, path)
      .then((res) => {
        setResult(res);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError
            ? err.message
            : "Could not reach the PRISM backend.",
        );
        setStatus("error");
      });
  };

  return (
    <div className="border-t hairline p-4">
      <h3 className="text-xs font-medium uppercase tracking-wide text-ink-dim">
        Ownership
      </h3>
      <p className="mt-1 text-xs text-ink-faint">
        Who understands this code — weighted by recent, well-understood
        changes, not blame.
      </p>

      <label className="mt-3 block">
        <span className="text-xs text-ink-faint">
          File or directory (blank for the whole repo)
        </span>
        <input
          className="input-dark mt-1 font-mono text-xs"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") run();
          }}
          placeholder="src/auth.py"
          spellCheck={false}
          aria-label="File or directory path"
        />
      </label>

      <button
        onClick={run}
        disabled={status === "loading"}
        className="btn-quiet mt-3 text-xs"
      >
        {status === "loading" ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <Users size={14} />
        )}
        {status === "loading" ? "Scoring…" : "Find owners"}
      </button>

      {status === "error" && error && (
        <p className="mt-3 text-xs text-danger">{error}</p>
      )}

      {status === "ready" && result && <OwnershipResult result={result} />}
    </div>
  );
}

function OwnershipResult({ result }: { result: OwnershipResponse }) {
  return (
    <div className="mt-4">
      <p className="text-xs text-ink-faint">
        {result.commit_count} {result.commit_count === 1 ? "commit" : "commits"}{" "}
        {result.path ? (
          <>
            touching <span className="font-mono">{result.path}</span>
          </>
        ) : (
          "across the repo"
        )}
      </p>

      <ul className="mt-3 space-y-3">
        {result.owners.map((owner) => (
          <li key={owner.login}>
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium text-ink">
                {owner.login}
              </span>
              <span className="font-mono text-xs text-ink-dim">
                {Math.round(owner.score * 100)}
              </span>
            </div>
            <div className="mt-1.5 h-1 overflow-hidden rounded bg-elevated">
              <div
                className="h-full rounded bg-accent transition-all duration-300"
                style={{ width: `${Math.round(owner.score * 100)}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-ink-faint">
              {owner.lines} {owner.lines === 1 ? "line" : "lines"} ·{" "}
              {owner.commits} {owner.commits === 1 ? "commit" : "commits"}
            </p>
            {owner.evidence.length > 0 && (
              <ul className="mt-1.5 space-y-1">
                {owner.evidence.map((line) => (
                  <li
                    key={line}
                    className="truncate font-mono text-xs text-ink-dim"
                    title={line}
                  >
                    {line}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>

      {result.related_paths.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-dim">
            Similar code
          </p>
          <ul className="mt-2 space-y-1">
            {result.related_paths.map((p) => (
              <li key={p} className="font-mono text-xs text-accent">
                {p}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
