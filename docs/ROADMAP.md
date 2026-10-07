# PRISM — 3-Week Build Roadmap

> 5–15 small, meaningful commits per day. Every commit deployable.

## Week 1 — Ingest & Understand

**Days 1–2: Foundation**
- [x] Repo scaffold, docs, CI, Docker
- [x] FastAPI skeleton with health checks
- [x] Next.js skeleton with design system

**Days 3–5: Git parsing**
- [x] Clone + walk history with GitPython (paginated, background jobs)
- [x] Per-commit file stats, diff extraction
- [x] Timeline JSON API (`GET /repos/{id}/timeline`)

**Days 6–7: Intent engine**
- [x] Groq integration, intent prompt engineering
- [x] "Why / what bug / what risk" per commit, cached
- [x] Commit inspector UI (2D panel)

## Week 2 — 3D & Intelligence

**Days 8–10: 3D time machine**
- [x] R3F canvas: commit nodes on time axis
- [x] File "buildings" extruded by churn
- [x] Camera fly-through + scrubber

**Days 11–12: Conflict prediction**
- [x] Tree-sitter AST extraction per branch
- [x] Overlap analysis → conflict probability
- [x] Branch compare UI

**Days 13–14: Semantic ownership**
- [x] Qdrant embeddings for code chunks
- [x] Ownership scoring (intent-weighted, not blame)
- [x] Ownership view UI

## Week 3 — Harden & Ship

**Days 15–17: Polish**
- [x] Search, filters, keyboard shortcuts (⌘K palette with commit search + actions, query/author filters that dim non-matching 3D nodes, "/" focuses filter, ↑↓/Esc kept)
- [x] Loading/error/empty states (ingest progress surfaced from job polling, error boundary around the scene with retry, actionable empty states)
- [x] Mobile fallback (2D timeline) (SVG 2D commit graph on small screens / coarse pointers / no WebGL, same selection + filter dimming)

**Days 18–19: Deploy**
- [x] Backend → Render (live: https://prism-api-te0e.onrender.com — Docker, Singapore, free tier; keep-alive cron pings /health every 5 min; `render.yaml` blueprint in repo)
- [ ] Frontend → Vercel (needs the Vercel repo import: set NEXT_PUBLIC_API_URL to the Render URL before deploying, then set PRISM_CORS_ORIGINS to the Vercel domain)
- [x] Docker Compose for self-host (PRISM_ env prefixes fixed, decorative Qdrant sidecar dropped, persistent /data volume)
- [x] Demo repo pre-loaded (PRISM_DEMO_REPO ingested on startup, GET /repos/demo status, "Live demo" button in the empty state)

**Days 20–21: Launch**
- [ ] Demo video, README polish
- [ ] Performance pass, docs
- [ ] v1.0 tag
