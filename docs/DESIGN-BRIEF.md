# PRISM — Frontend Design Brief
**Project:** PRISM — AI-Powered Git Time Machine (3D interactive Git history explorer)
**Date:** 2026-09-30
**Constraint from user:** Must NOT look like generic "AI slop." Must feel like a professional developer tool. Must be deployed, not just a repo.

---

## 1. Developer-tool design languages worth emulating

The best dev tools (Linear, Raycast, Vercel, Warp, GitKraken, GitHub) have converged on one shared discipline. It is not a skin — it is a philosophy:

### The shared rules
- **Near-monochrome + ONE accent.** Premium interfaces use surprisingly little color: a neutral ramp (near-black → near-white) plus a single accent doing all the heavy lifting. Color carries *meaning*, never decoration: accent = primary action/selection, red = danger, green = success, amber = warning.
- **Borders are nearly invisible.** White at ~5–8% opacity on dark (`rgba(255,255,255,0.06)`). Borders define regions; they are not a design element. Elevation is communicated through background-color steps, not shadows.
- **Typography IS the brand.** One UI typeface + one mono. No display-font mixing. Tight negative tracking on headings, tabular numerals on stats. Type does the expressive work that gradients do in slop.
- **Density over decoration.** 13–14px body text, compact rows, information-rich panels. Every element earns its place. Feels fast and precise.
- **Keyboard-first.** ⌘K command palette as primary navigation, visible keyboard shortcut chips, `←/→`/`space`/`esc` affordances. A blank-canvas resting state with a command bar beats a toolbar of buttons.
- **Motion with real easing.** 150ms hover, 300ms state change, eased camera/layout transitions. Never `linear`, never default `ease`.
- **Darkness as the native medium.** Not a dark theme applied to a light design — information hierarchy is managed through gradations of white opacity, not color variation.

### Per-tool notes
| Tool | Steal this | Ignore this |
|---|---|---|
| **Linear** | Near-black canvas `#08090A`, surfaces `#101113`, indigo accent `#5E6AD2`, Inter 510-weight labels, hairline borders | Marketing aurora gradients (keep them off the product UI) |
| **Raycast** | Command palette as the app's front door; near-black `#0D0D0D`; keyboard chips next to every action; single accent | — |
| **Vercel dashboard** | Functional monochrome, Geist/Geist Mono, borders-not-shadows, quiet Lucide icons at 16px | — |
| **Warp** | Terminal-grade density, mono metadata everywhere, warm near-black `#121212`, elevation via bg steps | Lifestyle-marketing nature photography |
| **GitKraken / GitLens** | Dense commit-graph visualization, color-coded branches, inline contextual detail, right-side inspector panels | Cluttered toolbars |
| **GitHub (Primer)** | Utilitarian density, subtle borders, status colors with fixed semantics | — |

### Pro vs. AI slop, concretely
- Pro: one accent, used on selection/active/focus only. Slop: purple→blue gradients on every card and button.
- Pro: 12–14px dense UI text, mono for hashes/dates/stats. Slop: 18px+ marketing body copy inside a tool.
- Pro: flat surfaces, hairline dividers. Slop: glassmorphism, glow shadows, floating orbs.
- Pro: real data in the first viewport (the 3D explorer IS the hero). Slop: a hero section *describing* the tool above the actual tool.

---

## 2. Prior art in 3D code/git visualization

### What was built
- **Gource** (acaudwell/gource): animated tree of files with contributors flying in, beams on file touch. The reference for "watch a repo evolve." A browser port (gource-view) now exists with MP4 export.
- **CodeCity** (Wettel, 2007 paper; modern impls e.g. firaslatrech/codecity): city metaphor — buildings = files/classes, districts = packages/folders, height = complexity/LOC, color = language. Modern versions bake analysis to JSON, render with instanced meshes in Three.js, orbit controls, click-to-inspect.
- **GitHub Skyline**: contribution graph extruded into 3D-printable STL. GitHub sunset the microsite; community replaced it with CLI tools (gh-skyline). Novelty, not analysis.
- **Code Flower / Software Galaxies / CodeCharta**: radial/force layouts of dependency structure.
- **git-truck / repo-visualizer**: bubble/treemap views of repo structure and temporal coupling.
- **GitLens**: the anti-3D reference — visualization embedded *in the workflow* (inline blame, commit graph sidebar, hover detail). Dense, contextual, zero disorientation.

### Interaction patterns that WORK
1. **Stable spatial metaphor.** The city works because brains already read skylines: height = size/complexity, district color = language, position = stable across time. Keep node positions fixed; animate only height/glow over time.
2. **Orbit + click-to-inspect, not free-fly.** OrbitControls (rotate/zoom/pan) with damping. Click selects → persistent right sidebar shows detail. One modern CodeCity fork explicitly killed cursor tooltips in favor of a persistent sidebar — tooltips in 3D are unreadable.
3. **Double-click to isolate.** Render the focused node's subtree only, re-laid out to fill the stage; breadcrumb/Esc to go back up. Hierarchy: repo → folder → file.
4. **Map-style labels.** Labels chosen dynamically by zoom level (district names → file names → symbol names), fading in/out like a map engine. Never label everything at once.
5. **Bottom timeline scrubber.** A video-editor-style time cursor over a commit-density histogram; scrubbing sets time T, highlights files touched near T, sidebar lists commits around T; play button animates.
6. **Instanced rendering for scale.** Buildings as `InstancedMesh`, cap at ~3,500 largest files, quality auto-scaling. Bake analysis to JSON once; the renderer never touches git.

### What FAILED (and why)
- **Gource-style pure playback** — HN's verdict: "pretty but useless." Mesmerizing, zero analytical agency. *Lesson for PRISM: the timeline must be scrubbable and queryable, not just playable. Every frame must answer "why did this change?"*
- **VR code cities** — studies show no comprehension gain, worse interaction efficiency. *Lesson: stay on flat screens with orbit controls.*
- **Unlabeled / rainbow 3D graphs** — disorientation and color noise. *Lesson: restrained palette, labels by zoom, one accent.*
- **Skyline-style novelty** — fun once, no workflow. *Lesson: PRISM's 3D must be the fastest path to an answer (who owns this? what broke? will this merge conflict?), not a screensaver.*
- **Tooltip-only inspection in 3D** — unreadable at angle/distance. *Lesson: persistent 2D inspector panel.*

### PRISM's differentiator vs. all of the above
Nobody shows **intent**. Gource shows *what moved*; CodeCity shows *what is big*; PRISM shows *why it changed, what risk it introduced, and what will conflict* — the LLM layer is the product, the 3D is the navigation. The 3D must therefore be **boring-in-a-good-way infrastructure** for the AI answers, not the star of the show.

---

## 3. Concrete recommendations for PRISM

### 3a. Color palette (dark-first, exact values)
Derived from Linear's token discipline, tuned for a 3D canvas:

| Role | Hex | Usage |
|---|---|---|
| App canvas | `#08090A` | Page background; also the 3D scene clear color (seamless blend) |
| Surface | `#101214` | Left rail, right inspector, timeline bar |
| Elevated | `#1A1D21` | Popovers, command palette, tooltips, dropdowns |
| Hover | `#22262C` | Row hover states |
| Border | `rgba(255,255,255,0.07)` | 1px dividers, panel edges |
| Border strong | `rgba(255,255,255,0.14)` | Focused/active panel edges |
| Text primary | `#F2F3F5` | Headings, primary labels |
| Text secondary | `rgba(242,243,245,0.65)` | Body, descriptions |
| Text muted | `rgba(242,243,245,0.40)` | Timestamps, hashes, metadata |
| **Accent** | `#5E6AD2` (indigo) | Selection, active states, primary CTA, focus rings, "current time" marker |
| Accent subtle bg | `rgba(94,106,210,0.14)` | Selected row wash, highlighted node glow |
| Success | `#4CB782` | Tests passing, clean merge prediction |
| Warning | `#F2C94C` | Merge-conflict risk, refactor risk |
| Danger | `#EB5757` | Destructive actions, high-risk commits |

**3D scene colors (must match the UI, not fight it):**
- Scene background/fog: `#08090A` (identical to app canvas — the canvas disappears into the page).
- File buildings: neutral zinc ramp by height (`#2A2E35` → `#8A8F98`), NOT rainbow. Height = churn/complexity.
- District (folder) base plates: `#101214` with hairline edges.
- Language coding: maximum 6 muted language colors at ≤65% saturation (e.g. TS `#5E8AD2`, Python `#7AB8A0`, Go `#6FC3DF`, Rust `#D08A5E`, JS `#D2C35E`, other `#8A8F98`). Districts, not buildings, carry language color — and only as a thin edge tint.
- Commit nodes: small spheres/pills in accent `#5E6AD2`; the *selected* commit gets a white core + accent halo. Risky commits (predicted conflict) pulse amber `#F2C94C`.
- Owner highlighting: selecting an author tints their touched buildings with accent wash; everything else desaturates.

### 3b. Typography
- **UI font:** `Inter` (variable, via `next/font`). Enable OpenType `cv11`/`ss03` for cleaner forms. Scale: 12px labels/meta, 13–14px body, 16–20px panel titles, 28–32px empty-state headings only. Headings weight 500–600, tracking `-0.01em` to `-0.02em`.
- **Code/mono font:** `JetBrains Mono` (or `Geist Mono`). Used for: commit hashes, file paths, timestamps, stats, keyboard shortcut chips, the ⌘K input. Always `tabular-nums` for numbers.
- **Rules:** one UI family + one mono, no exceptions. No serif, no display font. Uppercase micro-labels (`10–11px`, `tracking 0.08em`, muted) for section headers in the inspector.

### 3c. Layout — main 3D explorer view
An IDE-like shell, not a landing page. Full-viewport app (no scroll):

```
┌──────────────────────────────────────────────────────────────┐
│ ▸ slim top bar (48px): ⌘K command input | repo switcher |    │
│   branch selector | view tabs (Timeline / Owners / Risks)     │
├──────────┬──────────────────────────────────┬────────────────┤
│ left rail│                                  │ right inspector│
│ (56px    │        3D CANVAS (full-bleed)    │ (320px,        │
│ icons +  │                                  │ collapsible)   │
│ 240px    │   commits = nodes on time rails  │                │
│ expand)  │   files = buildings on ground    │ selected commit│
│          │                                  │ or file detail │
│ repo     │                                  │                │
│ tree /   │                                  │ Why / What /   │
│ filters  │                                  │ Risk cards     │
├──────────┴──────────────────────────────────┴────────────────┤
│ bottom timeline (96px): commit-density histogram + time       │
│ cursor scrubber + play/pause + speed + date readout (mono)    │
└──────────────────────────────────────────────────────────────┘
```

- **Top bar:** the repo URL input lives in the ⌘K command palette (paste URL → fuzzy-find → Enter to analyze), not a big centered hero input. Branch selector and analysis-status pill (queued/analyzing/ready) sit right.
- **Left rail:** icon rail (Explorer, Timeline, Owners, Merge-risk, Settings) expanding to 240px panel with repo file tree + filters (author, date range, file type). Collapsible to icons.
- **Center:** the 3D canvas, full-bleed, scene bg = app canvas color. Floating (not carded) minimal overlays: zoom-to-fit button, camera preset dropdown, legend (bottom-left, tiny, mono).
- **Right inspector (320px):** the money panel. On commit select: hash (mono, copyable), author + avatar, date, **"Why this changed"** (LLM intent), **"What it touched"** (file list with mini diff stats), **"Risk"** (conflict/risk assessment with severity chip). On file select: ownership (semantic owner, not just blame), recent commits touching it, complexity stats.
- **Bottom timeline:** histogram of commit density over time (accent bars on dark), draggable time cursor, play/pause (space), speed selector, current date readout in mono. Scrubbing is the primary "time travel" control.
- **Entry state:** if no repo loaded, the canvas shows a quiet empty state — small centered card (surface bg, hairline border): "Paste a repository URL" + ⌘K hint + 3 sample repos. No hero, no gradient, no feature grid.

### 3d. Interaction patterns for "flying through time" (without disorientation)
1. **Orbit by default, never free-fly.** `OrbitControls` with damping, min/max polar angle, min/max distance. Users already know this from every 3D tool; WASD-fly is a game, not a dev tool.
2. **Time travel = scrub, not flight.** Dragging the timeline moves a glowing time-cursor plane through the scene; buildings grow/shrink and commit nodes ignite as the cursor passes. The camera stays put unless the user moves it. This separates *temporal* navigation (timeline) from *spatial* navigation (orbit) — the #1 anti-disorientation rule.
3. **Camera presets with eased transitions.** Buttons: Overview / Top-down / Follow HEAD / Focus selection. Transitions tween position+target over ~600ms with cubic easing. Never cut.
4. **Double-click to isolate, Esc/breadcrumb to return.** Focus a folder → its subtree fills the stage; breadcrumb trail (mono, clickable) across the top of the canvas.
5. **Keyboard map (shown in a `?` overlay):** `←/→` step commit, `space` play/pause timeline, `esc` deselect/zoom-out, `⌘K` command bar, `1/2/3` camera presets, `f` focus selection.
6. **Selection model:** single selection, always reflected in *both* canvas (halo) and inspector (detail). Hover = subtle highlight + cursor change only; all reading happens in the persistent inspector.
7. **Motion discipline:** node ignitions fade (300ms), building height tweens on scrub (200ms), no perpetual idle animation except the selected-node halo. The scene should feel *still and precise*, not alive.

### 3e. What to AVOID — banned tropes
1. Purple/blue gradient backgrounds, buttons, or cards — anywhere, ever.
2. Glassmorphism (backdrop-blur cards over gradients) as a primary surface.
3. Emoji as UI icons. Use Lucide, 16px, `currentColor`, quiet.
4. "AI sparkle" (✨) iconography and "Powered by AI" badges. The AI is infrastructure; label features by what they *do* ("Intent", "Conflict prediction"), not by the fact they're AI.
5. Marketing hero sections inside the product (big headline + floating product shot + feature cards).
6. Gradient text headlines.
7. Chatbot-style centered chat as the primary interface. (A command bar + inspector is the interface; an "ask about this commit" thread can live *inside* the inspector as a secondary tab.)
8. Generic feature-card grids ("Blazing fast", "Secure", "Scalable" with stock icons).
9. Rounded-3xl cards with heavy drop shadows on dark backgrounds.
10. More than one accent color in the UI chrome. (Semantic red/amber/green are status, not accents.)
11. Auto-playing cinematic camera flights on load. Start still; let the user drive.
12. Lore ipsum / placeholder-looking sample content in the real UI. Empty states must be actionable (paste URL, try sample).

---

## 4. Tech recommendations

### React-Three-Fiber vs plain Three.js → **Use React-Three-Fiber**
PRISM is a Next.js app where React state (selected commit, time cursor, filters) *drives* the 3D scene, and the 3D scene drives React UI (inspector). That is exactly R3F's home turf:
- Declarative scene graph in JSX; selection/hover map naturally to React state.
- `@react-three/drei` gives `OrbitControls`, `Text` (billboard labels), `Html` (for label fallbacks), `CameraControls` (eased preset transitions) for free.
- `@react-three/postprocessing` for subtle bloom on the selected-node halo only.
- Ecosystem: `zustand` for 3D/UI shared state (the community-standard R3F pairing).

**Performance rules (non-negotiable):**
- Buildings = `THREE.InstancedMesh` (one draw call for thousands of files); update instance matrices on time-scrub, not per-frame React state.
- `useFrame` mutates refs only — never `setState` inside the render loop. Discrete UI state (selected id, time cursor) lives in zustand/React.
- `frameloop="demand"` when the scene is static (no timeline playing) to save battery.
- Cap rendered files (~3,500 largest), bake git analysis to JSON on the backend; the renderer never touches git.
- R3F adds ~570KB over vanilla Three.js — irrelevant for a desktop dev tool, and the velocity gain is large.

Use plain Three.js only if: the scene ever needs millions of individually-managed objects or hand-rolled shaders beyond postprocessing — not PRISM's case.

### UI component library → **shadcn/ui (new-york style) on Radix + Tailwind v4**
- It *is* the Linear/Vercel visual language: zinc/neutral tokens, hairline borders, `--radius` scale, dark-mode-first via `.dark` class, Geist/Inter pairing. You get the pro aesthetic by default instead of fighting a library's opinions.
- Primitives needed map 1:1: `command` (⌘K palette), `resizable` (rail/inspector panels), `sheet`/`dialog`, `tooltip`, `dropdown-menu`, `tabs`, `badge` (severity chips), `skeleton` (analysis loading), `scroll-area`, `slider` (timeline).
- Radix = accessibility-correct behavior (focus traps, ARIA) for free — matters for keyboard-first tools.
- Convention: build feature components in `components/prism/*` composed from `components/ui/*` primitives; theme via CSS tokens (`bg-background`, `text-muted-foreground`, `border-border`) — never raw hex in components.
- **Custom-build only:** the 3D canvas itself and the bottom timeline scrubber (no library does a commit-density histogram scrubber well).

### Backend / deployment pairing (for the "deployed, not just a repo" requirement)
- **Frontend:** Next.js (App Router) → **Vercel**. R3F is SSR-sensitive — the canvas component must be a client component with `dynamic(..., { ssr: false })`.
- **Backend:** FastAPI (GitPython for history parsing, tree-sitter for AST, Qdrant for semantic code search, Groq for intent summarization) → **Railway** or **Render** (simplest Docker deploy); Fly.io if you want regions. Ship a `Dockerfile` from day one.
- **Contract:** backend bakes analysis to a versioned JSON artifact (`city.json`-style: layout + per-commit intent + risk scores); frontend renders it. Long analyses run as background jobs with progress over websocket/SSE — never leave the user staring at a spinner (the CodeCity lesson).

---

## 5. Build order (first-week slice, for the 3-week plan)
1. App shell (top bar, rails, inspector, timeline) with **mock data** — nail the pro aesthetic before any 3D.
2. R3F canvas: static city from a baked sample JSON (one mid-size repo), orbit + select + inspector wiring.
3. Timeline scrubber wired to building heights/node ignition.
4. Backend: clone → GitPython parse → JSON artifact endpoint.
5. LLM intent per commit (Groq) → inspector "Why/What/Risk" cards.
6. Merge-conflict prediction + ownership views; deploy frontend + backend; polish pass against the banned-tropes list.

*Sources consulted: Linear/Raycast/Warp design-system references, dev-tool UX research 2024–2025, Gource, CodeCity (Wettel paper + firaslatrech/codecity + bryan-uipath/code-city DESIGN.md), GitHub Skyline community discussion, R3F decision frameworks, shadcn/ui conventions.*
