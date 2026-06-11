# Deep Diagnostic Audit — 2026-06-11

Scope: every failure mode that causes data to not be collected, charts to not populate, or articles/projects to go undetected. Based on code inspection, the 2026-06-08 weekly run log (`run_week_20260608_110228.log`), `docs/data/*` inspection, the live validator run (0 FAIL / 17 WARN), database state, and scheduled-task state.

Verdict: **the product is shipping every week, but roughly half of its advertised intelligence inputs are silently dead.** The validator and scheduler layers are healthy; the discovery and signals layers have systemic silent-failure rot. Every recent run is status `partial` and nobody is notified.

---

## CRITICAL — breaks the weekly product

### C1. L7 rerank catastrophically dropped ~5,800 articles on 2026-06-08 (fix deployed but never live-tested)
- Run log lines 231/272/276: `NIM Rerank: kept 0, dropped 5043 / 167 / 628`. Every article that survived L6 classification was discarded by L7. Net result: only ~100 projects extracted from a 25,176-article Google News haul.
- Fix (fail-open on unscored logits + 20% sanity floor that distrusts the rerank and keeps the full L6 set) was committed post-mortem on 2026-06-10 (`article_filter.py:744-810`). **It has never executed in a production run.** First live exercise is Monday 2026-06-15.
- Action: dry-run Phase 3 against a cached article set before Monday, or watch the 6/15 run log for `[Filter L7 DEGRADED]` / sane kept-counts.

### C2. Phase 3 budget (2400s) is mathematically insufficient; timeout loses work
- 6/08 run: 922 items → 60 extraction chunks ÷ 6 workers × 180–300s/chunk ≈ 1,800–2,500s for extraction alone, before L6/L7/dedup. Phase timed out; 331 queued articles were dropped (`Timeout after 2400s`, status `partial`).
- The 6/10 recall-fix added `extraction_backlog` persistence (cap 400, rerank-priority, 3-attempt expiry), but the flush happens every 5 completed chunks inside the `as_completed` loop (`phases/filtering.py:507-525`); the abandon-on-phase-timeout path has not been verified to leave a complete backlog. Chunks that time out at the Claude subprocess level (2 did on 6/08) are not added to `failed_articles` (`phases/filtering.py:240`, 468-475) — those articles are lost with no record.
- Action: raise the Phase 3 timeout (extraction is the long pole; 3600–4800s), and persist the full pending queue at phase entry, not incrementally.

### C3. Job monitor has produced ZERO data in every run since March
- `docs/data/jobs.json`: every week `{"data": {}, "spikes": []}`. Root cause: Indeed RSS (`ca.indeed.com/rss`) was discontinued by Indeed years ago — feedparser returns an empty feed with no error (`job_monitor.py:94`). Job Bank RSS URL is unverified. All exceptions log at DEBUG (`job_monitor.py:107-108`).
- Downstream: Claude Calls 1–3 receive empty hiring-spike context every week; the briefing's labour-signal integration is a no-op.
- Action: replace Indeed with sources that exist (Job Bank RSS verified live, Adzuna API free tier, or StatCan job-vacancy proxies), and make a 0-posting fetch a loud warning.

### C4. Procurement monitor has produced ZERO contracts in every run since March
- `docs/data/procurement.json`: every week `{"contracts": []}`. Causes, compounding:
  - Dead sources still in the chain: BuyAndSell RSS (DNS-dead), Ontario BPS CKAN (package removed upstream), BC Bid legacy RSS (platform retired). SaskTenders/Alberta Purchasing are dark (no public API).
  - Every fetcher swallows exceptions and returns `[]` (`procurement_monitor.py:171-176, 206-215, ...`).
  - `MIN_CONTRACT_VALUE = $5M` + construction-keyword match filters out ~95% of disclosed contracts, silently (no dropped-count logging) (`procurement_monitor.py:43, 148-153`).
  - SEAO (QC) and DCC PDF sources were added 6/10 and live-verified once, but have not produced data in a real run yet.
- Action: verify Open Canada/CanadaBuys/SEAO/DCC yield in a standalone run; log per-source fetch counts and filter-drop counts; consider lowering the $5M floor or making it province-scaled.

### C5. Tier 13 (municipal, 15 CMAs) returns 0 — every scraper is broken
- Run log: `[TIER 13] 0 municipal projects found`. Vancouver/Calgary/Edmonton/Winnipeg open-data APIs return HTTP 400 (query/schema drift); Hamilton, Québec City, Saskatoon, Regina, St. John's, Fredericton, Charlottetown, Oshawa, St. Catharines, Barrie, Abbotsford all 404 (site redesigns); Kelowna 403 (WAF).
- Action: fix the four big open-data API queries first (Vancouver/Calgary/Edmonton/Winnipeg are stable platforms; the 400s are likely parameter drift), then re-verify or retire the HTML scrapers.

### C6. Tier 14 (institutional: universities, hospitals, airports, ports) returns 0 — all ~40 endpoints broken
- Run log: `[TIER 14] 0 institutional projects found`. Every endpoint 404/403/SSL-fail, including several marked "live-verified" in `SOURCE_ENDPOINTS_NEEDS_LIVE_VERIFICATION.md` (UOttawa, Queen's, UManitoba, BC Children's…). IWK SSL failure persists despite a patch-1.2 fix claim. YVR/Port Vancouver/Port Montreal are TLS-fingerprint bot-blocked (403) — a plain requests client will never get through.
- Action: this tier needs a rebuild, not URL patches — prefer RSS/news-release feeds and Google News site-scoped queries over HTML scraping for bot-blocked domains.

### C7. Under the Microscope is `null` in production
- `docs/data/microscope.json` contains literally `null`. `microscope_history` key does not exist in `dashboard_state`. `select_microscope_topic()` can return None silently (Groq timeout / no headlines), in which case `store_microscope_history()` is never called, and `export_microscope()` (`tools/export_dashboard.py:887-897`) dumps `None` to disk with no null-check and no validator FAIL.
- Action: make the export raise/WARN on missing history; make topic-selection failure loud; add a validator check that microscope.json is non-null.

---

## HIGH — silent degradation, monitoring blindness

### H1. No failure notification anywhere
- Every recent run is `partial`. No email/Slack/push on crash, validator FAIL, or partial status. The scheduled tasks log only to the Claude Code task history. A tier that is 100% dead is indistinguishable from a quiet news week — this is the root enabler of C3–C6 going unnoticed for 3 months.
- `rss_feed_health.py` and `service_health.py` write health tables that **no run report ever reads**.
- Action: end-of-run health summary (per-tier yield vs trailing 8-run median, per-source failure counts) printed in the run log AND pushed as a notification; `[TIER DEGRADED]` already exists for 2 consecutive zero runs — surface it to the operator.

### H2. Two provincial EA registries down
- NB EIA: 4× HTTP 404 → returns `[]` silently. BC EAO: log shows 404 on the *old* `/api/v2/projects` endpoint even though a patch claimed to fix it — the fix may not be in the deployed code path. YESAB (Yukon) returns 0 with no error logged (opaque). Other 9 registries + IAAC working.

### H3. Tavily exhausted for June (2000/2000)
- Cost-finding, verification, named tracking, enrichment silently no-op until 2026-07-01 (monthly auto-reset confirmed at `db.py:2083-2096`; agent-reported "no reset logic" is incorrect). Newly discovered projects this month will systematically lack values. June's exception (2,000) reverts to the standing 1,000 in July.

### H4. Groq fallback is effectively decorative at pipeline volume
- 6K TPM free tier ≈ one 40-article batch per minute; `batch_classify()` passes everything after the first throttled batch through fail-open. If NIM has an outage mid-run, classification quality silently collapses. No 429 backoff in either client (`nim_client.py:147` raises; `groq_client.py:154` catches and fail-opens).

### H5. Policy tracker drops 93% of items
- 6/08 run: 30 items fetched from 17 feeds → 2 classified as investment-relevant. The classifier bar appears mis-tuned; 28 items vanish with no per-item record. Policy context feeding the briefing is near-empty.

### H6. Markets data: field-name contract mismatch (`val` vs `value`)
- briefing JSON writes `"val"` for all equities/FX; validator (and possibly other consumers) expect `"value"` (`tools/validate_briefing_schema.py:75-78` vs `briefing_latest.json` fx/indices). Data exists (timeseries has fresh tsx/sp500/fx points) — this is a naming drift between assembler and contract. 10 WARNs every run.

### H7. Run-level counters never wired → monitoring blind
- `projects_updated` initialized but never incremented (`pipeline_logging.py:55`); `fuzzy_merges` returned by `project_sync.py:506-518` but never logged to the run; `status_changes` only counted at export. All read 0 every week, so a total failure of status monitoring (Tier 4) would be invisible — and may already be occurring.

### H8. Phases 1–4 failures still deploy
- All four are `recovered=True` → conductor builds the briefing from stale/empty context and the run can even finalize as `success` (`update_dashboard.py:299-302` only flags `_analysis_incomplete` from agent failures). Only Phase 5 (conductor) failure blocks. Editorial invariant "no briefing content without real data" is not structurally enforced for signals/indicators.

### H9. Stale and broken chart series (charts that can never render)
- `canola`: 1 point — **never implemented** (empty tickers + TODO at `canadian_markets.py:72-85`).
- `uranium`: 1 point (U-UN.TO fetched once on 5/19, never again).
- 6 Ontario provincial series last updated **2021-04** (5 years stale); QC permits/exports/employment 345d stale; ~20 of 86 series exceed 60d.
- Any tldr-charts spec touching these dataKeys produces a blank or single-dot chart. The validator's dataKey cross-check protects the briefing's chosen charts, but the chart agent's usable palette is quietly shrinking.

### H10. Tier 12 (Google Alerts) silently disabled
- `[Tier 12] Skipped — no Google Alert feeds configured`. An entire advertised tier is off with a single log line.

---

## MEDIUM — robustness and hygiene

- **M1. Non-atomic JSON export.** `export_all()` writes 20+ files sequentially with plain `open(...,"w")`; a mid-export crash leaves the frontend in a torn state. This already happened: `timeseries.json.corrupt_20260514`. Use temp-file + `os.replace` per file.
- **M2. yieldCurveLastYear all-or-nothing.** One missing historical term drops the whole comparison line (`phases/data_collection.py:1850` length-equality check).
- **M3. Missing top-level aliases** `bocRate` / `pipeline_value` / `project_count` (validator WARN; assembler never writes them).
- **M4. Missing DB indexes** on `projects.province/status/sector/lastSeen` — full scans on a 7k-row, frequently-filtered table.
- **M5. Backup sprawl.** 12 × ~110MB `dashboard.db.pre-*` copies in the repo dir; the weekly SKILL.md "keep 4" rotation rule is not automated.
- **M6. Timeout margins.** Whole run took 9,559s on 6/08; conductor alone is allowed 7,200s. No wall-clock budget for the scheduled task; a hung conductor blocks until killed.
- **M7. RSS feed rot.** 153/333 feeds yielded items in the last run; the other 180 are unknown-dead — health table exists but is never reported (see H1).
- **M8. Claude extraction retries cap at 2** (180s → 300s); 2 chunks died on 6/08 with API fallback disabled, ~40 articles unrecorded.
- **M9. Equity/FX, snippet, dedup fail-opens are good** — but semantic dedup pass-through on NIM-embed outage (no dedup at all) can double-write evidence on a bad day. Acceptable, but worth a log line.

---

## What is healthy (verified)

- Validator gate: 0 FAIL, enforced at export and in both scheduled tasks (exit 1 blocks publish, exit 2 ships). Archive append-only protection in place.
- Scheduling: both Claude routines enabled; daily ran this morning (07:02), weekly next fires Mon 6/15 05:35.
- Tier 1 registries: 9 of 14 working (IAAC, Infra Canada, CER, QC, AB, SK, MB, NS, NL, MVRB, Metrolinx).
- Tier 2/2b: Google News (638 deduped feeds) + Bing News both producing (25k+ articles/week).
- Git: main in sync with origin; Pages deploy current as of 6/10.
- WAL mode + FK enforcement on; Tavily monthly auto-reset exists.
- Snippet enhancer, MinHash/semantic dedup, fail-open L6 classification all functioning per 6/08 log.

---

---

# PART 2 — PROSE AUDIT (extension, 2026-06-11)

Scope: the shipped briefing narrative (`briefing_latest.json`, week_of 2026-06-08, ~18,200 words), the writing-agent chain (tldr-conductor → writers 3A–3F/TRIAD → assembler → charts → auditor → fixer), and editorial/factual integrity. Method: full-text banned-word/placeholder scan, citation-integrity check, week-over-week rehash check, a 64-claim fact-check of prose numbers against `indicators.json` / `timeseries.json` / `commodities.json` / `projects_all.json` / `dashboard.db`, and a code audit of every enforcement gate.

## What's healthy in the prose layer

- **Editorial voice: compliant.** One banned-word hit in the entire briefing ("disappointing") and it sits inside a quoted PM statement — attribution, not editorializing. Zero placeholders, zero empty sections.
- **Coverage: complete.** All 13 provinces carry full prose (analysis 1,800–2,400 chars + labourDeepDive + consumerPulse + sectorHighlights + marketContext); 20 industries, 4 global regions, all commentary fields present except `wcs_analysis`.
- **No rehash.** 0% 8-word shingle overlap between this edition's executive summary / market commentary and the prior edition — prose is genuinely rewritten weekly.
- **Citations resolve.** 64 distinct `<sup>n</sup>` ids used, 141 sources, zero dangling references, every source has a valid http URL.
- **Indicator-derived prose is clean: 21/21 claims verified exactly** — unemployment, CPI, GDP, employment rate, housing starts, trade balance, and all ON/QC/AB provincial blocks match `indicators.json` to the decimal. (Including ON CPI 6.8% y/y, which the prose itself flags as anomalous — correct behavior.)
- **Validator prose gates are real:** banned words (15-word list) FAIL the deploy across all analysis fields; callout contract (60–240 chars, ≥1 data point, pipeline reference, banned-word subset) FAILs; citation integrity FAILs; section presence (13 provinces, headline non-empty, market arrays) FAILs.

## P-CRITICAL — factual errors shipped in the current edition

### P1. Web-search-sourced market numbers contradict the pipeline's own data (17 of 64 claims MISMATCH)
The fact-check splits cleanly by lineage. Claims derived from pipeline data verify; claims the writer sourced from web search contradict the shipped data files, and several are stale prior-edition values relabeled as current:
- **Wheat "$671.75/bu, fresh 52-week high"** — this value appears nowhere in the wheat series. Actual June 5–8: $580–583, ~13% below the claim and *falling*; the 52-wk max is $667.25 (May 19). The clearest unsupported number in the briefing.
- **Potash "$98.45, +5.3% on the week"** — $98.45 is the *prior edition's* (May 15/19) value carried forward; actual current is $94.02–94.69 and the true weekly change is **-1.7% — direction inverted**.
- **Silver "$56.01/oz"** — actual $68.43–68.94; off by ~$12.50 (-18%). Year-ago value also wrong.
- **GoC 10Y "3.45%" and 2s10s "58 bps, down 12"** — actual 3.48–3.53 and 61–66 bps; both legs of the spread claim wrong, internally consistent only with the wrong 10Y.
- **WTI/Brent May-19 baselines ($103.02/$110.14)** — actual 107.77/111.28; stated declines (-10.7%/-11%) understate the real -15.3%.
- **CAD "weakened 1.7% on the week"** — no window in the data produces 1.7%.

### P2. "On the week" systematically mislabels a ~2.5-week gap
Gold -3.6%, CAD -1.7%, WTI -10.7% are all May-19-baseline → June-5/8 moves (the inter-edition gap) framed as weekly moves. The framing is structural — the writer's "week over week" is actually "since last edition."

### P3. Project-cohort numbers in prose/callouts are not reproducible
"7,170 active projects ($1,306B)" (in 3 callouts), ON "728 projects / $448.9B", sector cohorts (power_energy 722/$486B, mining 348/$237.5B, gold 96/$54.2B…) — none reproducible from `projects_all.json` or `dashboard.db` (current: 6,302–6,375 / $1,113–1,476B; ON 648–666 / $191–291B; gold 69/$23.4B). Partial legitimate cause: the DB was consolidated **after** generation (06-09/06-10 dedup-merge + the 06-11 cleanup that deleted 524 below-threshold rows), and no 06-08 DB snapshot exists in docs/data to arbitrate. But gaps like ON $448.9B vs $191–291B and gold $54.2B vs $23.4B exceed what those cleanups explain. **Consequence either way: the published prose and the published project explorer now disagree with each other on the same page.**

### P4. Nine macro claims are unverifiable against any shipped data
+88,000 May employment, April -27,500, +115,500 swing, core trim/median, gasoline +28.6%, mortgage rates, US payrolls, ECB pricing, starts baseline 239,747 — all carry citations to external web sources but cannot be checked against any pipeline data file. Externally sourced ≠ wrong, but they sit outside every automated verification path.

## P-HIGH — generation-chain gaps that allowed this

- **P5. No automated numeric fact-check anywhere in the chain.** The auditor agent's Test 1 (number verification) is post-hoc, discretionary prose-reading; a PASS-WITH-WARNINGS verdict does not dispatch the fixer. Nothing reconciles prose numbers against `timeseries.json`/`indicators.json`/`projects_all.json` mechanically. This is exactly the hole P1–P3 shipped through — indicator prose is clean because writers copy from the injected dossier; market prose rotted because writers also WebSearch.
- **P6. Project counts are snapshotted into prose with no generation-time stamp.** Post-generation DB cleanups silently invalidate published claims, and with no same-day DB snapshot there is no way to audit which side drifted. Counts in prose should be written from (and validated against) the same export the edition ships with.
- **P7. Under the Microscope has no agent and no gate.** It's generated by `phases/narrative.py` (not a Claude skill); topic-selection failure is silent; no validator check that microscope output exists (confirms Part 1 C7).
- **P8. Per-province sub-field completeness is not validator-enforced.** `provinces.length == 13` is checked; an empty `labourDeepDive` inside a province would ship. (Word-count floors live only in writer self-check assertions.)
- **P9. Extended editorial vocabulary unenforced.** The validator's banned list is 15 words; `editorial_rules.md`'s extended list (robust, significant, strong/weak-as-judgment, good/bad news) is advisory only.
- **P10. Citation URL specificity loosely enforced.** Non-empty URL passes; a homepage citation (unverifiable claim) would not FAIL.
- **P11. HTML safety is frontend-only.** Writers emit raw HTML merged unsanitized; DOMPurify at render time in app.js is the only XSS barrier. One layer, but it does exist.

## Prose fix order

1. **P5 — add a mechanical fact-check gate**: a post-assembly validator phase that extracts every `<strong>`-wrapped numeric claim adjacent to a known entity (commodity, index, FX pair, indicator, project-count pattern) and reconciles it against the shipped data files; FAIL on contradiction, WARN on unverifiable. This one gate would have caught wheat, potash, silver, 10Y, the baselines, and the 7,170-project callouts.
2. **P1/P2 — constrain market writers to pipeline data**: market/commodity prompts must use injected timeseries values for any price the pipeline tracks (WebSearch only for context/events, never for prints the data files already carry), and must label the May-19→current move "since last edition," not "on the week."
3. **P3/P6 — same-snapshot discipline**: write project counts from the edition's own export; archive a DB/export snapshot per edition.
4. **P7 — microscope agent + validator gate** (with Part 1 C7).
5. **P8/P9/P10 — validator hardening**: per-province field floors, extended banned list, homepage-citation rejection.

---

## Recommended fix order (bullet-proofing sequence)

1. **Observability first (H1, H7)** — per-tier/per-source yield + failure summary at end of every run, pushed as a notification; wire the three dead counters. Without this, every other fix can silently regress again.
2. **Verify the 6/15 run survives (C1, C2)** — pre-test L7 sanity guard + extraction backlog on cached data; raise Phase 3 timeout.
3. **Resurrect the two zero-output signal feeds (C3, C4)** — jobs and procurement are briefing-advertised inputs that have never worked.
4. **Fix microscope export (C7)** and the `val`/`value` contract (H6) — visible product defects.
5. **Triage discovery rot (C5, C6, H2)** — big-4 municipal open-data APIs, NB/BC EAO registries; rebuild or retire Tier 14.
6. **Chart data debt (H9, M2, M3)** — implement canola or remove it; fix uranium refresh; refresh/retire 2021-era ON series; relax yield-curve check.
7. **Hygiene (M1, M4, M5, M6)** — atomic writes, indexes, backup rotation, run wall-clock budget.
