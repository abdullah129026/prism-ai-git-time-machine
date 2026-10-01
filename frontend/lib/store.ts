import { create } from "zustand";

interface PrismState {
  /** Repo URL typed into the top bar / empty state. */
  repoUrl: string;
  /** Repo id returned by the ingest API once Days 3–5 land; null until then. */
  repoId: string | null;
  /** Currently selected commit SHA, or null when nothing is selected. */
  selectedCommit: string | null;
  setRepoUrl: (url: string) => void;
  setRepoId: (id: string | null) => void;
  selectCommit: (sha: string | null) => void;
  reset: () => void;
}

export const usePrismStore = create<PrismState>((set) => ({
  repoUrl: "",
  repoId: null,
  selectedCommit: null,
  setRepoUrl: (repoUrl) => set({ repoUrl }),
  setRepoId: (repoId) => set({ repoId }),
  selectCommit: (selectedCommit) => set({ selectedCommit }),
  reset: () => set({ repoUrl: "", repoId: null, selectedCommit: null }),
}));
