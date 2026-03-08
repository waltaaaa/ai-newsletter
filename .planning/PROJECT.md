# CAN-MACRO Strategic Dashboard

## What This Is

A weekly intelligence briefing platform covering Canadian national economic conditions, provincial policy, capital projects, markets, and events. A Python discovery pipeline (14 tiers) fetches primary-source data, runs AI analysis, and publishes to a static HTML frontend via GitHub Pages. Data stored in SQLite, exported as static JSON. Designed to run autonomously every Monday via GitHub Actions with a ~$60/year budget.

## Core Value

Automated, factual, source-cited weekly intelligence on Canadian capital projects and economic conditions — no editorializing, no fabricated data, every claim traceable to a primary source.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ 14-tier discovery pipeline (government registries, RSS, GDELT, municipal, institutional) — v1.0
- ✓ Government registry scrapers (IAAC, BC EAO, NRCan, Infrastructure Canada, CanadaBuys) — v1.0
- ✓ RSS feed monitoring (201+ feeds, 6-layer filter, government bypass) — v1.0
- ✓ Google News RSS search (759 compound queries, replaces Gemini grounded search) — v1.1
- ✓ Tavily targeted enrichment (1000 credits/month free tier) — v1.1
- ✓ Claude Sonnet reasoning for all analysis tasks — v1.1
- ✓ Gemini Flash classification/extraction (no grounding) — v1.0
- ✓ Project dedup with evidence merge and status non-regression — v1.0
- ✓ 8-section weekly briefing generation with citation audit — v1.0
- ✓ Under the Microscope deep-dive section — v1.0
- ✓ Briefing export (PDF + DOCX) — v1.0
- ✓ Single-file HTML dashboard with Firestore backend — v1.0
- ✓ Primary-source enforcement (API values always win over AI) — v1.0
- ✓ Confidence scoring with decay after 30 days — v1.0
- ✓ Wayback Machine archival — v1.0
- ✓ Municipal development application scrapers (15 CMAs) — v1.0
- ✓ Key people RSS tracking with government bypass — v1.0
- ✓ Known-project sweep (208 Gemini queries + 47 hardcoded seeds) — v1.0
- ✓ Province normalization and GDP threshold fixes — v1.1
- ✓ Firestore dedup audit and merge — v1.1
- ✓ Interactive Chart.js indicator explorer — v1.1

### Active

<!-- Current milestone: v2.0 Infrastructure Overhaul — SQLite, GitHub Pages, Search Layer -->

- [ ] Firestore → SQLite migration via db.py single interface module
- [ ] Static JSON export (export_dashboard.py) for frontend consumption
- [ ] Frontend rewrite — replace Firebase SDK with fetch() to static JSON
- [ ] GitHub Pages deployment + GitHub Actions scheduled pipelines
- [ ] Missing project form — Google Form replacing Firestore writes
- [ ] Cleanup — remove .bak files, Firebase configs, dead code

### Out of Scope

<!-- Explicit boundaries with reasoning -->

- Gemini grounded search — Caused $136/day in charges. Permanently removed.
- Gemini Pro — Removed. All reasoning through Claude Sonnet only.
- Perplexity in weekly pipeline — Removed from weekly runs.
- GDELT as primary discovery — Reduced role due to network issues + cost.
- Mobile app — Web-first single-file SPA is sufficient.
- Real-time updates — Weekly cadence is the design.

## Context

- **Budget:** ~$60/year total. Claude ~$55/yr, Tavily free tier, Gemini Flash free tier.
- **Incident:** Gemini grounded search caused $136/day charges. API key disabled/deleted. v1.1 rebuilt search layer using free sources.
- **Model stack:** Claude Sonnet (all reasoning), Gemini Flash (extraction only, NO grounding).
- **Editorial policy:** Reporting only — no editorializing, no opinions, no recommendations.
- **Data:** 14 Firestore collections (migrating to SQLite), 201+ RSS feeds, 759 compound queries, 15 CMA scrapers.

## Constraints

- **Budget**: ~$60/year — no new paid services without explicit approval
- **Gemini**: NO grounding, NO `google_search` tool, NO `groundingConfig` — causes $35/1000 queries
- **Tavily**: 1,000 credits/month free tier hard cap
- **Model stack**: Claude Sonnet for reasoning, Gemini Flash for extraction only — do not change
- **Editorial**: Factual reporting only — no editorializing in any generated content
- **Data integrity**: URL hard gate (no URL = no database write), evidence merge never loses data, status never regresses, additive-only adaptive learning

## Current Milestone: v2.0 Infrastructure Overhaul — SQLite, GitHub Pages, Search Layer

**Goal:** Replace the entire infrastructure layer (Firestore → SQLite, Firebase Hosting → GitHub Pages, Cloud Functions → GitHub Actions) while keeping all business logic intact. Eliminates Google Cloud dependency and deployment complexity.

**Target features:**
- SQLite database via db.py single interface module (replaces Firestore)
- Static JSON export for frontend (replaces live Firestore queries)
- Frontend rewrite for static JSON (removes Firebase SDK entirely)
- GitHub Pages deployment from docs/ directory
- GitHub Actions scheduled workflows (weekly + daily)
- Google Form for missing project submissions
- Cleanup of .bak files and dead Firebase code

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Replace Gemini grounded search with Google News RSS | $136/day cost incident | ✓ Good — free, unlimited |
| Remove Gemini Pro entirely | Eliminate Google billing risk | ✓ Good — Claude Sonnet handles all reasoning |
| Tavily for targeted enrichment only | 1000/mo free tier sufficient for cost-finding, verification, tracking | ✓ Good — works within budget |
| Single-file HTML frontend | Simpler deployment, no build step | ⚠️ Reached 1,776 lines — resolved by extracting JS to app.js |
| Firestore for data storage | Managed, serverless | ⚠️ Replacing with SQLite in v2.0 — eliminate Google Cloud dependency |
| Firebase Hosting | Integrated with Firestore | ⚠️ Replacing with GitHub Pages in v2.0 — free, simpler |

---
*Last updated: 2026-03-07 after milestone v2.0 initialization*
