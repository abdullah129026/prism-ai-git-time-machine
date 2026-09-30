# PRISM Architecture

## System overview

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Next.js   │◄────►│   FastAPI    │◄────►│    Groq     │
│  frontend   │ HTTP │   backend    │ LLM  │  (intent,   │
│  (R3F 3D)   │      │              │      │   risk)     │
└─────────────┘      └──────┬───────┘      └─────────────┘
                           │
                    ┌──────┴───────┐      ┌─────────────┐
                    │ GitPython    │      │   Qdrant    │
                    │ Tree-sitter  │◄────►│  (semantic  │
                    │ (AST, diff)  │      │   search)   │
                    └──────────────┘      └─────────────┘
```

## Backend services

- `services/git_parser.py` — clone, walk history, extract per-commit file stats
- `services/intent.py` — LLM prompts that turn a diff + message into
  "why / what bug / what risk"
- `services/conflict.py` — AST-overlap analysis between two branches to
  predict merge conflicts before merging
- `services/ownership.py` — semantic code ownership via embeddings in Qdrant,
  weighted by intent history, not just blame recency
- `routers/repos.py` — ingest a repo URL, kick off background parsing
- `routers/analyze.py` — query endpoints: timeline data, conflict prediction,
  ownership graph

## Frontend

- Next.js App Router, TypeScript
- React Three Fiber canvas: commit nodes on a time axis, file "buildings"
  extruded by churn; camera flies along the timeline
- 2D overlay UI: repo input, commit inspector panel, branch compare,
  ownership view — pro dev-tool aesthetic (see design brief)

## Data flow

1. `POST /repos` with `repo_url` → clone to temp dir, persist job id
2. Background worker: GitPython walks commits → Tree-sitter parses changed
   files → Groq generates intent → Qdrant indexes embeddings
3. `GET /repos/{id}/timeline` → 3D-ready node graph JSON
4. `POST /repos/{id}/predict-conflict` with `base`, `head` → conflict report
5. `GET /repos/{id}/ownership` → semantic owners per file/module
