import { create } from "zustand";

import {
  fetchJobStatus,
  fetchTimeline,
  ingestRepo,
  type TimelineResponse,
} from "./api";

export type IngestStatus = "idle" | "ingesting" | "ready" | "error";
export type TimelineStatus = "idle" | "loading" | "ready" | "error";
export type ViewMode = "timeline" | "city";

interface PrismState {
  /** Repo URL typed into the top bar / empty state. */
  repoUrl: string;
  /** Repo id returned by the ingest API once parsing finishes. */
  repoId: string | null;
  /** Currently selected commit SHA, or null when nothing is selected. */
  selectedCommit: string | null;
  /** Ingest job lifecycle for the URL currently being explored. */
  ingestStatus: IngestStatus;
  ingestError: string | null;
  /** 3D-ready timeline data for the current repo. */
  timeline: TimelineResponse | null;
  timelineStatus: TimelineStatus;
  timelineError: string | null;
  /** Which 3D view the scene shows. */
  viewMode: ViewMode;
  setRepoUrl: (url: string) => void;
  setRepoId: (id: string | null) => void;
  selectCommit: (sha: string | null) => void;
  setViewMode: (mode: ViewMode) => void;
  /** Submit the URL, poll the ingest job, set repoId on success. */
  exploreRepo: (url: string) => Promise<void>;
  /** Fetch timeline JSON for the 3D scene. */
  loadTimeline: (repoId: string) => Promise<void>;
  reset: () => void;
}

const sleep = (ms: number) =>
  new Promise((resolve) => setTimeout(resolve, ms));

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong.";
}

const POLL_INTERVAL_MS = 1500;
const INGEST_TIMEOUT_MS = 10 * 60 * 1000;

export const usePrismStore = create<PrismState>((set, get) => ({
  repoUrl: "",
  repoId: null,
  selectedCommit: null,
  ingestStatus: "idle",
  ingestError: null,
  timeline: null,
  timelineStatus: "idle",
  timelineError: null,
  viewMode: "timeline",
  setRepoUrl: (repoUrl) => set({ repoUrl }),
  setRepoId: (repoId) => set({ repoId }),
  selectCommit: (selectedCommit) => set({ selectedCommit }),
  setViewMode: (viewMode) => set({ viewMode }),
  exploreRepo: async (url: string) => {
    const trimmed = url.trim();
    if (!trimmed) {
      set({
        ingestStatus: "error",
        ingestError: "Paste a repository URL first.",
      });
      return;
    }
    set({
      ingestStatus: "ingesting",
      ingestError: null,
      repoId: null,
      selectedCommit: null,
      timeline: null,
      timelineStatus: "idle",
      timelineError: null,
    });
    try {
      const { job_id } = await ingestRepo(trimmed);
      const deadline = Date.now() + INGEST_TIMEOUT_MS;
      for (;;) {
        await sleep(POLL_INTERVAL_MS);
        const job = await fetchJobStatus(job_id);
        if (job.status === "done") {
          if (!job.repo_id) {
            throw new Error("ingest finished without a repo id");
          }
          set({ repoId: job.repo_id, ingestStatus: "ready" });
          return;
        }
        if (job.status === "failed") {
          throw new Error(job.error || "ingest job failed");
        }
        if (Date.now() > deadline) {
          throw new Error("ingest timed out — try again");
        }
      }
    } catch (err) {
      set({ ingestStatus: "error", ingestError: errorMessage(err) });
    }
  },
  loadTimeline: async (repoId: string) => {
    set({
      timelineStatus: "loading",
      timelineError: null,
      timeline: null,
      selectedCommit: null,
    });
    try {
      const timeline = await fetchTimeline(repoId);
      if (get().repoId !== repoId) return; // repo switched mid-flight
      set({ timeline, timelineStatus: "ready" });
    } catch (err) {
      if (get().repoId !== repoId) return;
      set({ timelineStatus: "error", timelineError: errorMessage(err) });
    }
  },
  reset: () =>
    set({
      repoUrl: "",
      repoId: null,
      selectedCommit: null,
      ingestStatus: "idle",
      ingestError: null,
      timeline: null,
      timelineStatus: "idle",
      timelineError: null,
      viewMode: "timeline",
    }),
}));
