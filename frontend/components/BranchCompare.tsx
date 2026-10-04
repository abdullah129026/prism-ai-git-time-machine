"use client";

import { useState } from "react";
import { GitCompareArrows, Loader2 } from "lucide-react";

import {
  ApiError,
  predictConflict,
  type ConflictPrediction,
} from "@/lib/api";
import { usePrismStore } from "@/lib/store";

type Status = "idle" | "loading" | "ready" | "error";

function riskTone(probability: number): {
  label: string;
  text: string;
  bar: string;
} {
  if (probability >= 0.7)
    return { label: "High", text: "text-red-400", bar: "bg-red-400" };
  if (probability >= 0.3)
    return { label: "Medium", text: "text-amber-400", bar: "bg-amber-400" };
  return { label: "Low", text: "text-emerald-400", bar: "bg-emerald-400" };
}

/** Branch compare: pick two branches, get merge-conflict probability
 *  from AST overlap analysis. Lives at the bottom of the inspector. */
export default function BranchCompare() {
  const repoId = usePrismStore((s) => s.repoId);

  const [base, setBase] = useState("main");
  const [head, setHead] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<ConflictPrediction | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!repoId) return null;

  const run = () => {
    const b = base.trim();
    const h = head.trim();
    if (!b || !h) {
      setError("Enter both branch names.");
      setStatus("error");
      return;
    }
    setStatus("loading");
    setError(null);
    predictConflict(repoId, b, h)
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
        Conflict prediction
      </h3>
      <p className="mt-1 text-xs text-ink-faint">
        Which symbols both branches edit, and how likely the merge fights.
      </p>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className="block">
          <span className="text-xs text-ink-faint">Base</span>
          <input
            className="input-dark mt-1 font-mono text-xs"
            value={base}
            onChange={(e) => setBase(e.target.value)}
            spellCheck={false}
            aria-label="Base branch"
          />
        </label>
        <label className="block">
          <span className="text-xs text-ink-faint">Head</span>
          <input
            className="input-dark mt-1 font-mono text-xs"
            value={head}
            onChange={(e) => setHead(e.target.value)}
            placeholder="feature/…"
            spellCheck={false}
            aria-label="Head branch"
          />
        </label>
      </div>

      <button
        onClick={run}
        disabled={status === "loading"}
        className="btn-quiet mt-3 text-xs"
      >
        {status === "loading" ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <GitCompareArrows size={14} />
        )}
        {status === "loading" ? "Analyzing…" : "Predict conflict"}
      </button>

      {status === "error" && error && (
        <p className="mt-3 text-xs text-danger">{error}</p>
      )}

      {status === "ready" && result && (
        <CompareResult result={result} />
      )}
    </div>
  );
}

function CompareResult({ result }: { result: ConflictPrediction }) {
  const pct = Math.round(result.probability * 100);
  const tone = riskTone(result.probability);

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-ink-dim">
          {result.base} ← {result.head}
        </span>
        <span className={`text-xs font-medium ${tone.text}`}>
          {tone.label} · {pct}%
        </span>
      </div>
      <div className="mt-1.5 h-1 overflow-hidden rounded bg-elevated">
        <div
          className={`h-full rounded transition-all duration-300 ${tone.bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      <p className="mt-3 text-sm leading-relaxed text-ink-dim">
        {result.explanation}
      </p>

      {result.overlapping_files.length > 0 && (
        <ul className="mt-3 space-y-2">
          {result.overlapping_files.map((f) => (
            <li key={f.path} className="rounded border hairline bg-elevated p-2.5">
              <p className="font-mono text-xs text-ink">{f.path}</p>
              {f.symbols.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {f.symbols.map((s) => (
                    <span
                      key={s}
                      className="rounded border hairline bg-surface px-1.5 py-0.5 font-mono text-xs text-accent"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              )}
              {f.shared_lines > 0 && f.symbols.length === 0 && (
                <p className="mt-1 text-xs text-ink-faint">
                  {f.shared_lines} shared changed{" "}
                  {f.shared_lines === 1 ? "line" : "lines"}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
