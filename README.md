# PRISM — AI-Powered Git Time Machine

A 3D interactive Git history explorer that doesn't show code diffs — it shows **intent**.

`git log` tells you *what* changed. PRISM tells you *why* it changed, what bug it fixed,
what risk it introduces, and who truly owns the code — then lets you fly through
time in an interactive 3D timeline.

## What it does

- **Drop a repo URL** → PRISM clones and parses the entire Git history (GitPython)
- **Per-commit intent** → an LLM explains *why* each commit happened, what it fixed,
  and what risk it carries
- **3D time machine** → commits are nodes, files are buildings; fly through history
  with Three.js / React Three Fiber
- **Merge-conflict prediction** → analyzes overlapping AST changes (Tree-sitter)
  across branches *before* you merge
- **True code ownership** → semantic ownership, not `git blame` — who understands
  this code, not just who touched it last

## Stack

| Layer    | Tech |
|----------|------|
| Frontend | Next.js, React Three Fiber, TypeScript |
| Backend  | FastAPI, GitPython, Tree-sitter |
| AI       | Groq (LLM inference), Qdrant (semantic code search) |
| Deploy   | Vercel (frontend), Render (backend), Docker |

## Quick start

```bash
# backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# frontend
cd frontend
npm install
npm run dev
```

Or with Docker:

```bash
docker compose up --build
```

Set `PRISM_GROQ_API_KEY` in your shell (or a `.env` file) for commit-intent
analysis; `PRISM_DEMO_REPO` pre-loads a demo repository on first start.

## Deployment

**Backend (live):** Render web service `prism-api` (Docker, Singapore, free tier) —
https://prism-api-te0e.onrender.com. Deploys from `main`; the `render.yaml`
blueprint in the repo pins the same config. A GitHub Actions workflow pings
`/health` every 5 minutes to keep the free tier warm.

**Frontend:** import the repo in Vercel with the Next.js preset and set
`NEXT_PUBLIC_API_URL` to the backend URL *before* deploying (it is inlined at
build time). After the frontend URL is known, set `PRISM_CORS_ORIGINS` on the
backend to that domain.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the 3-week build plan.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

MIT
