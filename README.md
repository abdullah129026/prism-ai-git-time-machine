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
| Deploy   | Vercel (frontend), Railway (backend), Docker |

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

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the 3-week build plan.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

MIT
