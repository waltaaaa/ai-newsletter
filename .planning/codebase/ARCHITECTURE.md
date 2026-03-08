# ARCHITECTURE.md — System Architecture

## Pattern
Pipeline architecture — sequential data collection → AI analysis → Firestore persistence → static frontend rendering. No web server; frontend reads directly from Firestore via client SDK.

## Layers

### 1. Data Collection (No AI)
All fact-gathering happens before any AI calls. Primary sources always win over AI-generated values.

- **Government APIs:** BoC Valet, StatCan WDS, CMHC, FRED, ECB, BoE
- **Registry scrapers:** IAAC, BC EAO, NRCan, Infrastructure Canada, CanadaBuys
- **News discovery:** Google News RSS (759 queries), GDELT (reduced), RSS feeds (201+)
- **Enrichment:** Tavily targeted searches (1000/mo budget)
- **Markets:** Yahoo Finance (yfinance)
- **Municipal:** Open Data APIs (Socrata/CKAN) + HTML portals (15 CMAs)
- **Institutional:** U15 universities, polytechnics, hospitals (BeautifulSoup)

### 2. AI Analysis
All reasoning goes through Claude Sonnet. Gemini Flash handles only mechanical extraction/classification.

- **Claude Opus:** Executive summary, national analysis, global vectors (narrative prose)
- **Claude Sonnet:** Extraction, briefing, market commentary, policy assessment, Under the Microscope, gap analysis, extraction recovery, dedup QA, meta-analysis
- **Gemini Flash:** RSS classification, JSON extraction, Wayback parsing, enrichment queries

### 3. Persistence & Sync
- **Firestore writes:** `project_sync.py` → `upsert_projects()`, `upsert_flat_projects()` with dedup
- **State tracking:** `pipeline_state.py` — follow-up queries, JSON parsing
- **Confidence:** Scoring + decay (`confidence_decay.py`) after 30 days without re-discovery
- **Status:** Never regresses — merge logic always advances to highest status

### 4. Frontend Rendering
- Single-file SPA (`public/index.html`) reads Firestore directly
- Firebase Auth for access control
- Tabs: Dashboard, Macro (indicators + charts), Projects, Data Explorer (V-Code search)
- Chart.js for visualizations, Tailwind for styling

## Entry Points

| Entry Point | Purpose |
|------------|---------|
| `update_dashboard.py` | Main weekly pipeline (7-step process) |
| `update_dashboard.py --deep-sweep` | Monthly full sweep (all tiers at max) |
| `update_dashboard.py --seed-projects` | Full project seed from registries |
| `update_dashboard.py --test-feeds` | RSS feed URL validation |
| `update_dashboard.py --audit-citations` | Link rot audit |
| `seed_projects_v2.py` | Full project rebuild (Tier 1→2→3) |
| `known_project_sweep.py` | One-time ~208 Gemini queries + 47 hardcoded seeds |
| `run_weekly_briefing.py` | Briefing generation standalone |
| `functions/index.js` | Cloud Functions (weekly/daily triggers) |

## Data Flow

```
Government APIs ─┐
Google News RSS ──┤
GDELT Monitor ────┤──→ Article Filter (6-layer) ──→ Project Extraction
RSS Feeds (201+) ─┤                                     │
Tavily Search ────┤                                     ▼
Registry Scrapers ┘                              Dedup + Merge
                                                       │
                                                       ▼
BoC / StatCan / CMHC ──→ Primary Indicators ──→ Claude Analysis
Yahoo Finance ──────────→ Market Data ─────────→  (Opus + Sonnet)
                                                       │
                                                       ▼
                                                 Firestore Write
                                                       │
                                                       ▼
                                              public/index.html
                                             (reads Firestore directly)
```

## Key Abstractions

### Pipeline Config (`pipeline_config.py`)
Central configuration: model routing, NAICS map, province thresholds, status normalization, dedup logic, project schema factory (`make_project()`).

### Project Schema
All projects follow a strict schema defined in `pipeline_config.py`. Required fields: name, province, CMA, NAICS code, value, status, proponent, discovery_source, source URLs. Every project MUST have at least one verifiable source URL.

### RSS Filter (6 layers)
1. Government source bypass
2. Dollar-value bypass ≥ province GDP threshold
3. Below-threshold dampener
4. Keyword co-occurrence (~80 project + ~30 economic signals)
5. Negative keywords (crime/sports/weather only)
6. Gemini Flash classification (uncertain = RELEVANT)

### Confidence Scoring
Base 0.1, +0.1/evidence (max 0.3), +0.15/gov source (max 0.3), +0.1 verified value, +0.05-0.1 multi-tier. Decay after 30 days: 31-60d -0.05, 61-90d -0.10, 91-120d -0.15, 121+d -0.20.

### Dedup Strategy
`project_dedup.py` + `pipeline_config.py` — norm_key (name+province), fuzzy_match (0.85 threshold). Evidence arrays always merge (never overwrite). Status never regresses.

## Scheduling
- **Weekly:** Monday 6AM ET via Cloud Functions
- **Daily:** Midnight ET for incremental checks
- **Monthly:** `--deep-sweep` flag for full registry + Perplexity gap-fill
