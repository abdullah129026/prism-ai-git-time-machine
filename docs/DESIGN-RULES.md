# PRISM Design Rules — Banned Tropes

> Every UI commit must be checked against this list.
> Source: `docs/DESIGN-BRIEF.md` (frontend research, 2026-09-30).

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

## The short version

- Near-monochrome + ONE accent (`#5E6AD2` indigo). Color carries meaning, never decoration.
- Borders at ~7% white opacity. Elevation via background steps, not shadows.
- Inter for UI, JetBrains Mono for code/hashes/dates. 12–14px dense UI text.
- The 3D explorer IS the hero — no marketing hero sections inside the product.
- Keyboard-first: ⌘K palette, arrow keys, space, Esc. Shortcut chips visible.
- Motion: 150ms hover, 300ms state change, eased camera transitions. Never linear.
- Dark is the native medium: `#08090A` canvas, `#101214` surfaces, `#1A1D21` elevated.
