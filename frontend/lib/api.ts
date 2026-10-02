/** Typed client for the PRISM backend API. */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

export interface CommitSummary {
  sha: string;
  message: string;
  author: string;
  committed_at: string;
  additions: number;
  deletions: number;
  files_changed: number;
}

export interface CommitIntent {
  sha: string;
  why: string;
  bug_fixed: string | null;
  risk: string;
  confidence: number;
  model: string;
  generated_at: string;
}

export interface IntentResponse {
  repo_id: string;
  cached: boolean;
  commit: CommitSummary;
  intent: CommitIntent | null;
  intent_available: boolean;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    let detail = `request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* keep default */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

/** Why / what bug / what risk for one commit. Cached server-side. */
export function fetchCommitIntent(
  repoId: string,
  sha: string,
): Promise<IntentResponse> {
  return request<IntentResponse>(
    `/repos/${encodeURIComponent(repoId)}/intent/${encodeURIComponent(sha)}`,
  );
}

/** Warm the intent cache for the N most recent commits (background). */
export function warmIntentCache(
  repoId: string,
  limit = 20,
): Promise<{ started: boolean; repo_id: string; limit: number }> {
  return request(`/repos/${encodeURIComponent(repoId)}/intent/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ limit }),
  });
}
