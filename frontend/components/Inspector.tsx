"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Bug,
  CircleHelp,
  GitCommit,
  RefreshCw,
  X,
} from "lucide-react";

import { ApiError, fetchCommitIntent, type IntentResponse } from "@/lib/api";
import { usePrismStore } from "@/lib/store";
import BranchCompare from "@/components/BranchCompare";

type Status = "idle" | "loading" | "ready" | "error";

function shortSha(sha: string) {
  return sha.slice(0, 7);
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

/** Right-hand commit inspector: metadata + why / bug / risk intent. */
export default function Inspector() {
  const repoId = usePrismStore((s) => s.repoId);
  const selectedCommit = usePrismStore((s) => s.selectedCommit);
  const selectCommit = usePrismStore((s) => s.selectCommit);

  const [status, setStatus] = useState<Status>("idle");
  const [data, setData] = useState<IntentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    if (!repoId || !selectedCommit) {
      setStatus("idle");
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setStatus("loading");
    setError(null);
    fetchCommitIntent(repoId, selectedCommit)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError
            ? err.message
            : "Could not reach the PRISM backend.",
        );
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [repoId, selectedCommit, attempt]);

  return (
    <aside className="flex h-full w-80 shrink-0 flex-col border-l hairline bg-surface">
      <div className="flex items-center justify-between border-b hairline px-4 py-3">
        <h2 className="text-sm font-medium text-ink">Inspector</h2>
        {selectedCommit && (
          <button
            onClick={() => selectCommit(null)}
            className="inline-flex items-center gap-1 text-xs text-ink-faint transition-colors duration-150 hover:text-ink"
            aria-label="Clear selection"
          >
            <X size={14} />
            Clear
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {!selectedCommit && <InspectorEmpty />}
        {status === "loading" && <InspectorSkeleton />}
        {status === "error" && (
          <InspectorError message={error ?? "Unknown error"} onRetry={reload} />
        )}
        {status === "ready" && data && (
          <InspectorBody data={data} onRetry={reload} />
        )}
        <BranchCompare />
      </div>
    </aside>
  );
}

function InspectorEmpty() {
  return (
    <div className="p-4">
      <p className="text-sm text-ink-dim">
        Select a commit on the timeline to see its intent, risk, and file
        changes.
      </p>
      <div className="mt-4 space-y-2 text-sm">
        <p className="text-ink-faint">
          <span className="kbd">↑</span> <span className="kbd">↓</span> move
          between commits
        </p>
        <p className="text-ink-faint">
          <span className="kbd">Esc</span> deselect
        </p>
      </div>
    </div>
  );
}

function InspectorSkeleton() {
  return (
    <div className="space-y-3 p-4" aria-label="Loading commit intent">
      <div className="h-4 w-3/4 animate-pulse rounded bg-elevated" />
      <div className="h-3 w-1/2 animate-pulse rounded bg-elevated" />
      <div className="h-3 w-2/3 animate-pulse rounded bg-elevated" />
      <div className="mt-6 h-3 w-1/4 animate-pulse rounded bg-elevated" />
      <div className="h-16 animate-pulse rounded bg-elevated" />
      <div className="h-16 animate-pulse rounded bg-elevated" />
    </div>
  );
}

function InspectorError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="p-4">
      <div className="rounded border hairline bg-elevated p-3">
        <p className="text-sm font-medium text-ink">Couldn&apos;t load intent</p>
        <p className="mt-1 text-sm text-ink-dim">{message}</p>
        <button onClick={onRetry} className="btn-quiet mt-3 text-xs">
          <RefreshCw size={14} />
          Retry
        </button>
      </div>
    </div>
  );
}

function InspectorBody({
  data,
  onRetry,
}: {
  data: IntentResponse;
  onRetry: () => void;
}) {
  const { commit, intent } = data;

  return (
    <div>
      {/* Commit header */}
      <div className="border-b hairline p-4">
        <div className="flex items-start gap-2">
          <GitCommit size={16} className="mt-0.5 shrink-0 text-ink-faint" />
          <p className="text-sm font-medium leading-snug text-ink">
            {commit.message || "(no message)"}
          </p>
        </div>
        <p className="mt-2 font-mono text-xs text-accent">
          {shortSha(commit.sha)}
        </p>
        <p className="mt-1 text-xs text-ink-faint">
          {commit.author} · {formatDate(commit.committed_at)}
        </p>
        <p className="mt-2 font-mono text-xs">
          <span className="text-emerald-400">+{commit.additions}</span>{" "}
          <span className="text-red-400">−{commit.deletions}</span>{" "}
          <span className="text-ink-faint">
            · {commit.files_changed}{" "}
            {commit.files_changed === 1 ? "file" : "files"}
          </span>
        </p>
      </div>

      {/* Intent */}
      <div className="p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-medium uppercase tracking-wide text-ink-dim">
            Intent
          </h3>
          {intent && (
            <span className="text-xs text-ink-faint">
              {data.cached ? "cached" : "analyzed just now"}
            </span>
          )}
        </div>

        {!data.intent_available || !intent ? (
          <div className="mt-3 rounded border hairline bg-elevated p-3">
            <p className="text-sm text-ink-dim">
              Intent analysis is unavailable — the backend has no Groq API key
              configured.
            </p>
            <button onClick={onRetry} className="btn-quiet mt-3 text-xs">
              <RefreshCw size={14} />
              Retry
            </button>
          </div>
        ) : (
          <div className="mt-3 space-y-4">
            <IntentField
              icon={<CircleHelp size={16} className="text-ink-faint" />}
              label="Why"
              body={intent.why}
            />
            <IntentField
              icon={<Bug size={16} className="text-ink-faint" />}
              label="Bug fixed"
              body={intent.bug_fixed ?? "No bug fixed by this commit."}
              quiet={!intent.bug_fixed}
            />
            <IntentField
              icon={<AlertTriangle size={16} className="text-amber-400" />}
              label="Risk"
              body={intent.risk}
            />
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-ink-faint">Confidence</span>
                <span className="font-mono text-xs text-ink-dim">
                  {Math.round(intent.confidence * 100)}%
                </span>
              </div>
              <div className="mt-1.5 h-1 overflow-hidden rounded bg-elevated">
                <div
                  className="h-full rounded bg-accent transition-all duration-300"
                  style={{ width: `${Math.round(intent.confidence * 100)}%` }}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function IntentField({
  icon,
  label,
  body,
  quiet = false,
}: {
  icon: React.ReactNode;
  label: string;
  body: string;
  quiet?: boolean;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5">
        {icon}
        <span className="text-xs font-medium text-ink-dim">{label}</span>
      </div>
      <p
        className={`mt-1 text-sm leading-relaxed ${
          quiet ? "text-ink-faint" : "text-ink"
        }`}
      >
        {body}
      </p>
    </div>
  );
}
