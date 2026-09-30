# PRISM — 3-Week Build Roadmap

> 5–15 small, meaningful commits per day. Every commit deployable.

## Week 1 — Ingest & Understand

**Days 1–2: Foundation**
- [x] Repo scaffold, docs, CI, Docker
- [ ] FastAPI skeleton with health checks
- [ ] Next.js skeleton with design system

**Days 3–5: Git parsing**
- [ ] Clone + walk history with GitPython (paginated, background jobs)
- [ ] Per-commit file stats, diff extraction
- [ ] Timeline JSON API (`GET /repos/{id}/timeline`)

**Days 6–7: Intent engine**
- [ ] Groq integration, intent prompt engineering
- [ ] "Why / what bug / what risk" per commit, cached
- [ ] Commit inspector UI (2D panel)

## Week 2 — 3D & Intelligence

**Days 8–10: 3D time machine**
- [ ] R3F canvas: commit nodes on time axis
- [ ] File "buildings" extruded by churn
- [ ] Camera fly-through + scrubber

**Days 11–12: Conflict prediction**
- [ ] Tree-sitter AST extraction per branch
- [ ] Overlap analysis → conflict probability
- [ ] Branch compare UI

**Days 13–14: Semantic ownership**
- [ ] Qdrant embeddings for code chunks
- [ ] Ownership scoring (intent-weighted, not blame)
- [ ] Ownership view UI

## Week 3 — Harden & Ship

**Days 15–17: Polish**
- [ ] Search, filters, keyboard shortcuts
- [ ] Loading/error/empty states
- [ ] Mobile fallback (2D timeline)

**Days 18–19: Deploy**
- [ ] Frontend → Vercel, Backend → Railway
- [ ] Docker Compose for self-host
- [ ] Demo repo pre-loaded

**Days 20–21: Launch**
- [ ] Demo video, README polish
- [ ] Performance pass, docs
- [ ] v1.0 tag
