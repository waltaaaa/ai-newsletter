# Signal 49 branding — retrieval notes & frontend mapping

Reference material only. Nothing in `docs/index.html`, `docs/js/app.js`, or
`public/` was modified. Date: 2026-07-10.

---

## 1. Access failures (read this first)

**The live site could not be fetched from this environment.** Every retrieval
route failed with HTTP 403 because the sandbox's outbound network egress is
restricted to an allowlist (Anthropic hosts + package registries):

| Attempt | Result |
|---|---|
| `curl https://signal49.ca` via agent proxy | `CONNECT tunnel failed, response 403` — proxy status log: `connect_rejected … policy denial` for `signal49.ca:443` |
| `WebFetch https://signal49.ca` and `https://www.signal49.ca` | HTTP 403 |
| Wayback Machine (`web.archive.org`, `archive.org` API) | curl: `Host not in allowlist: archive.org`; WebFetch: explicitly blocked |
| Fetch proxies (`r.jina.ai`, `api.allorigins.win`, `api.codetabs.com`) | HTTP 403 |
| Control test: `WebFetch https://en.wikipedia.org/...` | HTTP 403 — confirms blanket egress block, not a Signal49-specific bot wall |

**What still worked:** WebSearch (Anthropic-side) — brand background facts
only, no CSS/hex/font data. And, crucially, **genuine Signal49 brand assets
were already present in this repo** (`docs/assets/signal49_logo.png`,
`signal49_favicon.png`, committed 2026-06-09) and were pixel-analyzed here.

**To complete the extraction later**, from a machine with open egress:

```
curl -sL https://www.signal49.ca/ -o home.html
grep -oE 'href="[^"]+\.css[^"]*"' home.html          # theme stylesheets (site is WordPress-family per subpage URL shapes)
grep -oE 'fonts\.(googleapis|gstatic)[^"]*' home.html # font loading
# then pull each CSS file and harvest :root custom properties / hex values,
# plus /wp-content/... logo SVGs and favicon variants.
```
Update `signal49-tokens.css` items marked `[TODO]`.

## 2. What Signal 49 is (from web search)

Signal49 Research is the renamed **Conference Board of Canada** (rebrand
effective 2026-01-26, external branding agency). "Signal" = clarity/insight;
"49" = the 49th parallel + Signal Hill, NL. Brand language: "clarity, trust,
and forward momentum … a dependable beacon." Canada's leading economic
research/forecasting organization — i.e., the same editorial register this
dashboard already targets (sober, evidence-based, wire-service tone).

Key pages (for later extraction): `/`, `/our-research/`, `/about-us/`,
`/about-us/announcement/`, `/press/a-new-name-for-a-bold-future/`, `/faq/`,
`/contact/`.

## 3. Verified brand elements (from the assets in `./assets/`)

### Logo — `assets/signal49_logo.png` (271×89)
Pure **white knockout wordmark** (single color `#ffffff`). Designed to sit on
navy/gradient backgrounds — exactly how `docs/index.html` already uses it in
the `.site-header` (Prussian-blue header, `drop-shadow` filter).

### Brand mark / favicon — `assets/signal49_favicon.png` (512×512)
Circular mark, three white dots (right two overlapping — a "signal"
motif), on a **left→right linear gradient** sampled at:

| Position | Hex |
|---|---|
| 0% (left) | `#1c3664` deep navy |
| 25% | `#214f77` |
| 50% | `#277393` |
| 65% | `#2b89a4` |
| 75% | `#2e97ae` |
| 100% (right) | `#35b9c8` bright teal |

CSS: `linear-gradient(90deg, #1c3664 0%, #277393 50%, #35b9c8 100%)`

This **navy→teal gradient is the strongest verified Signal49 signature**
available in this environment.

### Typography (unverified analog, already in repo)
The live site's font stack could not be confirmed. The repo's existing
convention (comment at `docs/index.html:1386`) treats **Inter** as a
"Neue Haas Grotesk analog" for all headings, with **IBM Plex Mono** for data
figures — both loaded from Google Fonts (see the `<link>` at
`docs/index.html:13`). Keep this until the real stack is extracted.

### Existing "Signal49-style" conventions in this repo (analogs, not verified)
- **Prussian blue `#003153`** — header, nav (`#00253f` darkened), active
  subtabs, hyperlinks, `--accent-blue`/`--accent`/`--accent-blue-soft`.
- **Red rule `#E3120B`** — 48×4px kicker bar atop editorial SVG charts
  (`docs/js/app.js:985`, "Signal49-style: red rule + uppercase kicker +
  Inter bold title + Inter italic deck").
- Uppercase, letter-spaced kickers; italic decks; tight heading tracking.

Note: the verified brand navy is `#1c3664` (warmer, lighter) — the repo's
`#003153` is an approximation adopted before the assets were analyzed.

## 4. Existing frontend styling (what a restyle would touch)

All styling is one inline `<style>` block in `docs/index.html` (~lines
21–1407; `public/index.html` is the synced source — **edit `public/`, deploy
via `tools/deploy_to_github.py`**). Chart colors live as JS constants in
`docs/js/app.js` (`BRAND`, `INK`, `MUTED`, `GRID`, and the `#E3120B` rule).

Current `:root` (docs/index.html:22–56): light `#f4f6f8` background, white
cards, `--accent-blue:#003153`, `--accent-red:#c4320a`, radii 8/12/16/24px,
soft shadows, Inter/IBM Plex Mono, 4–48px spacing scale.

## 5. Concrete mapping recommendations (do not apply yet)

1. **Brand navy**: change `--accent-blue`, `--accent-blue-soft`, `--accent`
   from `#003153` → verified `--s49-navy: #1c3664`. Also the hardcoded
   `#003153` occurrences: `.site-header` background + its `::after` gradient
   rgba stops, `.main-nav` (`#00253f` → a darkened navy, e.g. `#152a4f`),
   `.national-subtab.active`, `.edition-item:hover` color,
   `.newsletter-hero .hero-prose strong/sup`, and `_srcLink()`/`ind-src-link`
   styling (PATCH_LOG TLDR-25 hyperlink color).
2. **Signature gradient**: replace the `.site-header` Unsplash photo +
   Prussian overlay (`.site-header::before/::after`) with the brand gradient
   `var(--s49-gradient)` — the white knockout logo is designed for exactly
   this surface. Same gradient works as the active-tab underline or
   `.section-banner` accent edge.
3. **Teal as the secondary accent**: `--s49-teal: #35b9c8` for active-state
   highlights, focus rings, chart secondary series (app.js `secondaryColor`
   fallback), and link hover — currently the theme has no secondary accent.
   `--s49-teal-tint: #e7f6f8` for `--accent-blue-light`-style soft fills.
4. **Keep the red rule** `#E3120B` in `renderAgentInsightChart`/editorial SVGs
   unless live-site extraction shows Signal49 uses a different kicker color
   ([TODO] — verify; red-on-navy/teal is plausible but unconfirmed).
5. **Favicon**: `docs/index.html` currently declares no `<link rel="icon">`
   — add one pointing at `assets/signal49_favicon.png` (already shipped).
6. **Typography**: no change needed now (Inter + IBM Plex Mono already
   loaded); revisit heading weights/tracking once the real stack is known.
7. **Chart palette**: rebase `BRAND`/series colors in `docs/js/app.js` on the
   navy→teal ramp (`#1c3664 → #277393 → #35b9c8`) for sequential series —
   also load the `dataviz` skill before touching chart colors, and re-check
   the callout/chart validator contract (CLAUDE.md) after any app.js change.

## 6. Files in this directory

```
docs/branding/signal49/
├── DESIGN_NOTES.md            ← this file
├── signal49-tokens.css        ← CSS custom properties (provenance-tagged)
└── assets/
    ├── signal49_logo.png      ← white knockout wordmark, 271×89
    └── signal49_favicon.png   ← gradient brand mark, 512×512
```
