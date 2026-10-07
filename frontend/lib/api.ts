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

/* ------------------------------------------------------------------ */
/* Repo ingest (Week 1, Days 3–5): submit a URL, poll the background   */
/* job until the repo is parsed.                                       */
/* ------------------------------------------------------------------ */

export interface IngestJobResponse {
  job_id: string;
  status: string;
}

export interface JobStatus {
  job_id: string;
  repo_id: string;
  /** queued | cloning | parsing | ready | error - matches backend jobs.py */
  status: string;
  stage_detail: string;
  commits_parsed: number;
  error: string | null;
}

/** Submit a repo URL for background ingestion. Resolves with the job id. */
export function ingestRepo(repoUrl: string): Promise<IngestJobResponse> {
  return request<IngestJobResponse>("/repos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl }),
  });
}

/** Poll the status of an ingest job. */
export function fetchJobStatus(jobId: string): Promise<JobStatus> {
  return request<JobStatus>(`/repos/${encodeURIComponent(jobId)}`);
}

/* ------------------------------------------------------------------ */
/* Timeline (Week 2, Days 8–10): 3D-ready commit graph + file churn.   */
/* ------------------------------------------------------------------ */

export interface TimelineNode {
  sha: string;
  message: string;
  author: string;
  committed_at: string;
  parents: string[];
  additions: number;
  deletions: number;
  files_changed: number;
}

export interface TimelineEdge {
  source: string;
  target: string;
}

export interface FileChurn {
  path: string;
  additions: number;
  deletions: number;
  commits: number;
}

export interface TimelineResponse {
  repo_id: string;
  repo_url: string;
  commit_count: number;
  nodes: TimelineNode[];
  edges: TimelineEdge[];
  file_churn: FileChurn[];
}

/** 3D-ready timeline JSON: commit nodes on a time axis, parent edges,
 *  and per-file churn for the file "buildings" view. */
export function fetchTimeline(
  repoId: string,
  limit = 500,
): Promise<TimelineResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return request<TimelineResponse>(
    `/repos/${encodeURIComponent(repoId)}/timeline?${params}`,
  );
}

/* ------------------------------------------------------------------ */
/* Conflict prediction (Week 2, Days 11–12): AST overlap between two   */
/* branches, scored against their merge-base.                          */
/* ------------------------------------------------------------------ */

export interface ConflictFileOverlap {
  path: string;
  symbols: string[];
  shared_lines: number;
}

export interface ConflictPrediction {
  base: string;
  head: string;
  probability: number;
  overlapping_symbols: string[];
  overlapping_files: ConflictFileOverlap[];
  explanation: string;
}

/* ------------------------------------------------------------------ */
/* Semantic ownership (Week 2, Days 13–14): who understands this code, */
/* intent-weighted instead of git blame.                               */
/* ------------------------------------------------------------------ */

export interface OwnershipOwner {
  login: string;
  score: number;
  lines: number;
  commits: number;
  evidence: string[];
}

export interface OwnershipResponse {
  repo_id: string;
  path: string | null;
  commit_count: number;
  owners: OwnershipOwner[];
  related_paths: string[];
}

/** Ranked authors for a path (or the whole repo), plus files holding
 *  semantically similar code. */
export function fetchOwnership(
  repoId: string,
  path?: string,
): Promise<OwnershipResponse> {
  const params = new URLSearchParams();
  if (path?.trim()) params.set("path", path.trim());
  const query = params.toString() ? `?${params}` : "";
  return request<OwnershipResponse>(
    `/repos/${encodeURIComponent(repoId)}/ownership${query}`,
  );
}

/** Probability that merging `head` into `base` hits a conflict. */
export function predictConflict(
  repoId: string,
  base: string,
  head: string,
): Promise<ConflictPrediction> {
  return request<ConflictPrediction>(
    `/repos/${encodeURIComponent(repoId)}/predict-conflict`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ base, head }),
    },
  );
}
