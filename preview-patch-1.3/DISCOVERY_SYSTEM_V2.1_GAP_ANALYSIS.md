# DISCOVERY SYSTEM V2.1 — Gap Analysis & Revisions

**Status:** Second-pass red-team of DISCOVERY_SYSTEM_V2.md. Items marked **[LOCK NOW]** must be resolved before schema lock; items marked **[PILOT]** are bounded experiments; **[REJECTED]** documents ideas considered and dropped, with reasons.
**Date:** 2026-06-09

---

## Part 1 — Gaps in the v2 design, fixable now

### G1. Yield-weighted scheduler has a cold-start problem **[LOCK NOW]**

The stratified sweep allocates weekly slots by trailing 12-week yield — which doesn't exist on day one. An unseeded scheduler under-samples for three months.
**Fix:** Bootstrap stratum yields from the current system's learning-engine query-effectiveness logs (they already track per-query hit rates), and run a flat full sweep for the first 4 shadow weeks before the scheduler takes over. Mirrors the existing cold-start-protection pattern.

### G2. Lincoln-Petersen will lie to you **[LOCK NOW]**

LP assumes capture events are independent. Media coverage and registry presence are positively correlated (big projects appear everywhere), so LP **underestimates** the unseen population — false confidence in coverage, and it gates the second Claude window, so the error propagates into resourcing.
**Fix (three parts):**
1. Compute LP only across the most plausibly independent family pairs (lobbying×media, permits×media, registries×local-media) and label the output a **lower bound**, never a point estimate.
2. Add a second, independent estimator: a **Chao1-style accumulation curve** on weekly new-project discovery rates per stratum. When the curve flattens, the stratum is near-saturated; when it's still climbing, you're missing things. Trivial to compute from existing data.
3. Add a **canary set**: ~50 manually curated known-real projects spanning provinces, sectors, sizes, and lifecycle stages (sourced once from references). Weekly, measure whether the pipeline detects them and their state changes. This is direct recall measurement with zero statistical assumptions — the most honest instrument of the three.

### G3. Northern and Indigenous coverage is a structural blind spot **[LOCK NOW]**

v2 (and the current system) lists "13 provincial/territorial EA registries," but in the territories the real project gatekeepers are the **co-management boards**, which are separate bodies: **YESAB** (Yukon), **MVEIRB/MVLWB** (NWT Mackenzie Valley), and **NIRB** (Nunavut). All are enumerable public registries. Same for Indigenous-led projects nationally: **Indigenous Services Canada's infrastructure investment listings** are enumerable, and major Indigenous economic development corporations announce capital projects through channels none of the current tiers watch.
**Fix:** Add YESAB, MVEIRB/MVLWB, NIRB to Tier 1 (zero-miss invariant applies); add ISC infrastructure listings to Tier 3; add the top ~15 Indigenous development corporations to the Tier 5 corporate watchlist. This is the single largest *coverage* gap fixable now, and it strengthens exactly the under-threshold-but-significant northern strata where the $3M territorial thresholds live.

### G4. Stale procurement sources **[LOCK NOW]**

The project documentation still references **BuyAndSell**, which was retired — federal tenders and awards migrated to **CanadaBuys**, which publishes open data. Quebec's **SEAO** also publishes open tender data. Defence infrastructure flows through **Defence Construction Canada** award publications, which nothing in the current tiers watches.
**Fix:** Tier 4 becomes CanadaBuys open data + SEAO open data + DCC awards + provincial portals (BC Bid, SaskTenders, Alberta Purchasing Connection). All free, all enumerable.

### G5. Per-project tracking feeds won't scale as designed **[LOCK NOW]**

Two RSS feeds per entity × thousands of entities = thousands of daily polls. That strains Actions minutes and, more importantly, risks Google News throttling the runner's IP — which would degrade the *primary discovery sweep*, not just monitoring.
**Fix:** Tiered polling by lifecycle state and value: daily for pre-RFP and in-motion states above threshold; weekly for stable states (PERMITTING, CONSTRUCTION); monthly for dormant. Pool low-value projects into shared CMA-level feeds. Hard cap on total active feeds with value-ranked eviction. Polite jitter on all polls; SearXNG as the throttle fallback.

### G6. Gemini Flash is a single point of failure with a flood-mode failure state **[LOCK NOW]**

Free tiers change. v2's fail-open (pass everything through) is correct for an hour-long outage but catastrophic for a permanent deprecation — extraction volume would explode.
**Fix:** Define a **classifier failover chain** in code: Gemini Flash → NIM-hosted small instruct model (free tier, same JSON contract) → keyword-only mode with *tightened* thresholds (fail-degraded, not fail-flooded). The model-routing abstraction already exists; this is configuration plus one adapter.

### G7. Value semantics are underspecified in the schema **[LOCK NOW]**

"$5B project" can mean phase or program, CAD or USD, nominal or escalated, "up to" or committed. Retrofitting this later means re-extracting history.
**Fix — schema additions before lock:** `currency`, `value_low`/`value_high`, `value_scope: phase|program`, and a precedence rule: registry/filing-sourced values override media-sourced values regardless of recency. Also add `schema_version` to every record type now; migrations are inevitable.

### G8. Triangulation axes were never defined **[LOCK NOW]**

v2 ships `axes_satisfied` without saying what an axis is.
**Fix — lock the five axes:** (1) regulatory (Tier 1 observation), (2) financial/disclosure (Tier 2), (3) commercial (Tier 4 procurement/permits), (4) pre-public (Tier 5 lobbying/key-people/corporate), (5) media (Tier 6). Triangulation score = count of distinct axes with at least one observation. Clean, computable, and upgrade-compatible with the edges tier later.

### G9. French parity is asserted, not instrumented **[LOCK NOW]**

Bilingual queries exist, but the triage stack is anglo-centric: embedding centroids, keyword categories, and the regression corpus all need explicit French representation or French articles die quietly at L2/L4.
**Fix:** Separate French positive/negative centroids; French regression-corpus quota (≥25% of articles); per-language recall as a standing scorecard metric; QC/NB canaries discoverable only via French sources.

### G10. Claude session continuity **[LOCK NOW]**

If the Wednesday session doesn't run (travel, outage), fail-open holds, but adjudication backlog compounds silently and could falsely trigger the second-window criterion.
**Fix:** Manifest items carry over with an age-based priority boost; items older than 2 weeks auto-resolve to the conservative heuristic (pairs held distinct, transitions held pending) with a permanent `auto_resolved` flag; skipped sessions are excluded from second-window backlog counting.

### G11. Geocoding is solvable today, free and offline **[LOCK NOW]**

The map currently needs only province/CMA centroids, but city-level will be demanded eventually, and the right answer requires no API at all: **StatsCan census subdivision boundary files yield representative-point centroids for every municipality in Canada** — a one-time build of a static lookup table, same pattern as the StatsCan cache. No Nominatim, no paid geocoder, no runtime dependency.

### G12. Storage and rehash discipline **[LOCK NOW]**

Append-only observations grow without bound, and syndicated wire copy creates near-duplicate observations that inflate confidence.
**Fix:** Rehash detection (content-hash + near-dup embedding check) runs *before* observation write — syndicated copies attach to the original observation as `republications`, contributing zero confidence. Raw text compressed; raw text for Tier 6 observations prunable after 12 months (metadata and URLs kept forever — the URL hard gate is unaffected).

---

## Part 2 — Additional and better approaches

### A1. Corporate watchlist via sitemap/newsroom diffing **[ADOPT]**

Better than ad hoc agent searches of corporate channels: maintain ~200 proponents/EPCs (plus the Indigenous development corps from G3); weekly job diffs each newsroom's sitemap/RSS for new URLs and routes them into triage as Tier 5 observations. Deterministic, free, and catches investor-channel announcements with dollar values media coverage omits. This is the systematic version of catalog agent 1G.

### A2. Wikidata/Wikipedia alias harvesting **[ADOPT]**

Major Canadian projects have Wikidata entries and infoboxes carrying official names, alternate names, costs, and status. A monthly SPARQL/API job harvests aliases into entity `aliases[]` — directly attacking the entity-resolution alias problem (the harness's fuzzy-match pass exists precisely because aliases are the dedup killer). Free, low effort, high leverage on merge quality.

### A3. Municipal council agenda mining **[PILOT]**

Most large municipalities publish agendas through a handful of platforms (eScribe, Legistar, CivicWeb) with consistent structures. Keyword-scanning agendas for the top 15 CMAs catches projects at the *staff report* stage — earlier than development applications, squarely in the pre-RFP moat. Pilot 3 CMAs for 4 weeks; adopt if it produces ≥5 projects/month not found by any other tier first.

### A4. GDELT as a Tier 6 supplement **[PILOT — bounded]**

GDELT's Global Knowledge Graph indexes outlets beyond Google News RSS reach, free, every 15 minutes. Filtered to Canadian locations + infrastructure/economic themes it could catch small-market coverage. The cost isn't money, it's processing volume and noise. Pilot: one month of GKG filtering in shadow, count unique-first discoveries. Adopt only if it beats the council-agenda pilot per unit of pipeline complexity; otherwise drop without sentiment.

### A5. Tavily paid tier — concrete recommendation **[ADOPT, with guardrails]**

Pricing verified today: the Project plan is $30/month for 4,000 API credits on a sliding scale, and the free tier remains 1,000 credits/month; pay-as-you-go charges $0.008 per credit once a plan's credit limit is reached.

- **Adopt the $30/month Project plan (4,000 credits).** Fits the ceiling with $20/month headroom.
- **Guardrail 1:** the PAYG overage option must remain **disabled** — overage billing is exactly the structural risk class we eliminate. Hard cap stays enforced in SQLite at 4,000 with the usual buffer.
- **Guardrail 2:** ban Tavily's Research endpoint in code — third-party analysis reports it can consume up to ~250 credits in a single request, which is a budget bomb. Basic (1 credit) and advanced (2 credits) search only.
- **Reallocation of 4,000 credits:** cost-finding 1,200 · **pre-RFP corroboration 800 (new category — pre-RFP states are now first-class and need second-source verification most)** · named-project tracking 600 · deep verification 500 · French-language enrichment 400 (supports G9) · general enrichment 300 · buffer 200.

### A6. Event-sourced state, formalized **[ADOPT — costs nothing]**

Observations are already append-only; make lifecycle transitions and confidence recomputations append-only events too, with the entity table treated as a rebuildable projection. This makes every A/B comparison, calibration check, and "why did this project's status change" question answerable retroactively. It's a discipline declaration, not new infrastructure.

---

## Part 3 — Considered and rejected

| Idea | Why rejected |
|---|---|
| Vector database (Pinecone/Qdrant/pgvector) | Entity volume is tens of thousands, not millions. NIM embeddings + brute-force cosine in SQLite-adjacent NumPy is sub-second. Adds infra and billing surface for zero capability. |
| Graph database for triangulation | Minimum commitment tier already approved; the observation model makes edges recoverable later. A graph DB now is architecture for a decision not yet earned. |
| Common Crawl processing | Terabyte-scale for a weekly national pipeline on free Actions runners. GDELT pilot covers the same intent at 1/1000th the weight. |
| Paid news APIs (NewsAPI, Aylien, etc.) | $50/month buys shallow tiers of any of them; Google News RSS + curated feeds + GDELT pilot covers the surface free. Budget is better spent on Tavily depth. |
| Firecrawl/Exa as Tavily replacement | Genuine alternatives at higher volume, but switching costs (integration, budget logic) aren't justified while Tavily's 4,000 credits are unexhausted. Revisit only if the credit cap binds for 3+ months. |
| Real-time (sub-daily) discovery | The product is a weekly briefing. Daily registry watchers + tracking feeds already catch breaking changes. Sub-daily sweeps burn rate-limit headroom for no reader-visible benefit. |

---

## Part 4 — Updated artifacts and ordering

1. **Harness updated:** `ab_test_harness.py` now computes **time-to-discovery** on shared projects (who found it first, median lead in days). This was a gap in my own deliverable — the pre-RFP moat is a latency claim, and the A/B previously never measured latency.
2. **Schema lock checklist (supersedes v2 §13):** value semantics fields + schema_version (G7) · triangulation axes (G8) · tracking-feed tier policy fields (G5) · `republications` and `auto_resolved` flags (G12, G10) · entity-resolution bands · manifest caps.
3. **Source additions before shadow mode:** YESAB, MVEIRB/MVLWB, NIRB, ISC listings, Indigenous dev-corp watchlist (G3) · CanadaBuys, SEAO, DCC (G4) · corporate sitemap watchlist (A1).
4. **Instruments before shadow mode:** canary set + Chao1 curves + LP-as-lower-bound (G2) · per-language recall (G9) · French centroids and corpus quota (G9).
5. **Then:** flat-sweep bootstrap weeks (G1) → scheduler activation → pilots (A3, A4) → cutover per harness verdict.

Cost position after revisions: **$30/month** (Tavily Project plan), $20/month headroom, all other additions free.
