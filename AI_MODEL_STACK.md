# AI Model Stack

## Every Model Behind Signal Dispatch — What It Does, What It Costs, and Why It's There

Signal Dispatch runs on a multi-model architecture where each model handles the tasks it's best suited for. The guiding principle: use the most capable model only where capability matters, and use free or local models everywhere else. The result is a system that spends ~$150/year on AI while running 14 discovery tiers, processing thousands of articles, and generating a weekly intelligence briefing.

---

## The Core Stack

### Claude Opus 4.6 — The Writer

**Role:** All narrative writing
**Cost:** ~$120/year ($15/$75 per million input/output tokens)
**Provider:** Anthropic

Opus is the most capable model in the stack and the most expensive per token. It handles every task where prose quality directly affects the output readers see:

- **Call 1 (Macro Analysis):** Synthesizes national economic conditions — BoC rate decisions, employment data, GDP, CPI, building permits, housing starts — into narrative context. Receives policy summaries, hiring spikes, procurement awards above $10M, IAAC status changes, and extended StatsCan data as additional context.
- **Call 2 (Industry Analysis):** Analyzes sector-level trends with per-sector signals: policy items, hiring spikes, procurement awards.
- **Call 3 (Provincial Analysis):** Province-by-province analysis with per-province signals: policy items, hiring spikes, procurement awards, IAAC changes.
- **Weekly Briefing:** The 1,000-1,500 word intelligence report covering 8 sections — headline, macro pulse, Under the Microscope deep-dive, provincial spotlight, sector watch, project tracker, markets and commodities, and looking ahead.
- **Under the Microscope:** The 200-300 word deep-dive on the week's dominant story, connecting it to specific projects and indicators in the database.
- **Market Commentary:** 200-300 word factual summary connecting commodity and market price movements to specific Canadian projects by name.
- **Pre-Event Analysis:** 150-250 word forward-looking pieces for high-significance upcoming events (BoC decisions, budget releases, IAAC hearings).
- **Executive Summary:** Standalone narrative synthesis of the week's data for the briefing header.

Opus never touches extraction, classification, or mechanical tasks. Those go to cheaper models. The split is strict: if the output is read by humans as prose, Opus writes it.

### Claude Sonnet 4.6 — The Reasoner

**Role:** Extraction, reasoning, quality assurance
**Cost:** ~$30/year ($3/$15 per million input/output tokens)
**Provider:** Anthropic

Sonnet handles every analytical task that requires intelligence but doesn't need Opus-level prose:

- **Call 4 (Project Extraction):** Processes filtered articles in batch, extracting structured project records — name, proponent, location, value, status, type, sector, description, and evidence URLs. Receives sector and province hints from the metadata tagger.
- **Gap Analysis:** After discovery completes, analyzes results to identify what the pipeline might have missed this week.
- **Extraction Recovery:** Re-processes articles where initial extraction failed or returned incomplete data.
- **Dedup QA:** Reviews deduplication results for false positives (distinct projects merged) and false negatives (duplicates missed).
- **Signal Investigation:** Follows up on anomaly signals from building permits and lobbyist registries.
- **Monthly Meta-Analysis:** End-of-month review of pipeline performance, discovery patterns, and coverage gaps.
- **Policy Impact Assessment:** Classifies policy articles by category and links them to affected sectors, provinces, and specific projects.
- **Selective Extraction:** Re-extracts specific fields from articles when enrichment identifies gaps.

Sonnet is 5x cheaper per input token and 5x cheaper per output token compared to Opus. At the volume of extraction and reasoning calls the pipeline makes, this saves roughly $90/year versus routing everything through Opus.

**Cost cap:** A hard $8/run ceiling is enforced in code. If cumulative Claude spending in a single pipeline run hits $8, all remaining Claude calls are skipped. The typical weekly run costs $2-4.

### Gemini 2.5 Flash — The Classifier

**Role:** High-volume mechanical classification and extraction
**Cost:** $0 (Google AI free tier, no grounding)
**Provider:** Google

Gemini Flash handles every task that is high-volume but low-complexity:

- **RSS Article Classification (Layer 6):** The final layer of the 6-layer filter. Processes articles in batches of 20, returning structured JSON with relevance classification, province/sector assignment, event type, confidence score, and estimated value range. This is the single highest-volume LLM task in the pipeline — hundreds of articles per week.
- **Project Field Extraction:** Extracts structured data from article text (secondary to Claude's Call 4 extraction — used for bulk pre-processing).
- **Rehash Detection:** Identifies syndicated and duplicate articles across feeds before they consume extraction calls.
- **V-Code Search Fallback:** When the local StatsCan index can't match a user's data explorer query, Gemini Flash searches for the correct V-code. Discovered codes are saved to the local index so the same query never hits Gemini again.
- **Policy Article Classification:** Pre-classifies policy articles as POLICY_RELEVANT or NOT_RELEVANT before Claude's deeper assessment.
- **Topic Context Search:** Runs 2-3 web searches to gather latest context on the Under the Microscope topic before Claude Opus generates the deep-dive.

**Critical constraint:** The code never passes `google_search` tool or `groundingConfig` to the Gemini API. Enabling grounding costs $35 per 1,000 queries. This happened once during development and generated $136 in charges in a single day. The system now uses Google News RSS for all web discovery instead.

### Qwen 2.5 3B — The Local Fallback

**Role:** On-device article classification when available
**Cost:** $0 (runs locally via Ollama)
**Provider:** Alibaba (open-weight model, self-hosted)

A 3-billion parameter model running on Ollama (localhost:11434) that serves as a drop-in replacement for Gemini Flash's classification layer:

- **RSS Article Classification:** Binary RELEVANT/IRRELEVANT classification for the Layer 6 filter step. Uses a lean prompt that outputs numbered R/I verdicts instead of Gemini's 12-field JSON, cutting output tokens by ~50%.
- **Batch Processing:** Classifies up to 80 headlines per call using a compact numbered format.
- **Fail-Open Design:** If Ollama isn't running or the model isn't loaded, the system falls back to Gemini Flash transparently. If neither is available, all articles pass through (fail-open — false negatives are worse than false positives).

The local model eliminates network latency and API dependency for the highest-volume classification task. On machines where Ollama is running, it handles the entire Layer 6 workload without touching any external API.

---

## The Search & Enrichment Layer

### Tavily — Targeted Web Search

**Role:** Budget-constrained web search for enrichment tasks
**Cost:** $0 (1,000 credits/month free tier)
**Provider:** Tavily

Tavily is not used for broad discovery (Google News RSS handles that). It's reserved for targeted follow-up searches where the pipeline already knows what it's looking for:

| Task | Monthly Budget |
|------|---------------|
| Cost-finding for valueless projects | 300 credits |
| Named project tracking (top 50 by value) | 200 credits |
| Deep verification (single-source projects) | 200 credits |
| General enrichment (missing fields) | 150 credits |
| Signal investigation (permit/lobbyist follow-up) | 100 credits |
| Buffer | 50 credits |
| **Total** | **1,000 credits** |

Each basic search costs 1 credit. Credit tracking is enforced in SQLite — the pipeline stops enrichment searches when the monthly budget is exhausted (with a 50-credit buffer to avoid overshoot).

### SearXNG — Unlimited Free Web Search

**Role:** Unrestricted web search for deep discovery sweeps
**Cost:** $0 (self-hosted via Docker)
**Provider:** Self-hosted (open source)

SearXNG is a metasearch engine that aggregates results from multiple search backends (Google, Bing, DuckDuckGo, and others) without any API key, credit limit, or rate constraint when self-hosted.

The pipeline uses it as the search backbone for deep discovery sweeps:

- **Primary search for NIM deep search:** Feeds search results to the K2.5 extraction pipeline (replacing Moonshot's proprietary `$web_search`).
- **Snowball discovery:** Powers adaptive follow-up queries when the pipeline discovers a project and wants to find related ones.
- **Cost verification supplement:** Can supplement Tavily for cost-finding when the Tavily budget is tight.

**Search chain:** Local SearXNG (Docker) is tried first. If unavailable, a public SearXNG instance is used as fallback. If both fail, the search returns empty results gracefully.

No rate limit on localhost. Public instances may throttle, handled with retry backoff.

### Google News RSS — Primary Discovery Layer

**Role:** Broad news discovery across all provinces and sectors
**Cost:** $0 (unlimited, no API key)
**Provider:** Google

Not an AI model, but the single most important search mechanism in the stack. 2,574 compound queries are converted to Google News RSS feed URLs and polled weekly with 30-way parallelism. Returns 10-15 articles per feed. Processes the entire query set in under 60 seconds.

This replaced Gemini's grounded search, which was the source of the $136/day billing incident.

---

## The NIM Intelligence Layer

### NVIDIA NIM K2.5 (Thinking Mode) — Deep Extraction

**Role:** Structured project extraction from web search results with reasoning traces
**Cost:** $0 (NVIDIA free tier, 40 RPM shared across all NIM models)
**Provider:** NVIDIA

K2.5 in thinking mode replaced Moonshot's `moonshot-v1-128k` as the extraction model for deep discovery sweeps. The thinking mode enables chain-of-thought reasoning on ambiguous cases — when an article mentions a "$500M expansion" but doesn't specify whether it's a new phase or a revised cost estimate, K2.5's reasoning trace helps disambiguate.

Pipeline: SearXNG search results are reranked by NIM, top results have their full text extracted by trafilatura, and K2.5 processes the combined context to output structured JSON project records.

### NVIDIA NIM Reranker (rerank-qa-mistral-4b) — Relevance Scoring

**Role:** Filters and ranks search results before extraction
**Cost:** $0 (NVIDIA free tier)
**Provider:** NVIDIA

Sits between SearXNG search results and K2.5 extraction. Scores each search result for relevance to the original query, and only the top N results (default 5) proceed to full-text extraction and K2.5 processing. This eliminates noise from SearXNG's multi-engine results before spending extraction calls.

### NVIDIA NIM Embeddings (nv-embedqa-e5-v5) — Semantic Dedup

**Role:** Embedding-based project deduplication
**Cost:** $0 (NVIDIA free tier)
**Provider:** NVIDIA

Generates vector embeddings for project names and descriptions, enabling semantic similarity matching for deduplication. Catches cases that string-matching misses: "LNG Canada Phase 2" vs "Kitimat LNG Phase II" have different strings but similar embeddings.

Batch processing: up to 20 texts per API call.

### NVIDIA NIM PaddleOCR — Document Extraction

**Role:** PDF and image text extraction from government documents
**Cost:** $0 (NVIDIA free tier)
**Provider:** NVIDIA

Extracts text from provincial government PDFs — capital plans, EA decisions, budget documents — that aren't available as structured data. Provincial PDFs are the richest untapped source of project information; many provinces publish detailed capital spending plans as PDF-only documents.

---

## The Moonshot Legacy Layer

### Moonshot v1-128k (Kimi) — Deep Web Search

**Role:** Web-augmented project discovery (being replaced by NIM pipeline)
**Cost:** ~$8-10 per sweep
**Provider:** Moonshot AI (via Kimi API)

The original deep search model. Uses Moonshot's `$web_search` tool to search the web and extract project data from results, all in a single API call. Discovered ~1,400 projects across province-sector sweeps.

**Being replaced because:**
- Older, weaker extraction model compared to NIM K2.5
- Unknown search index quality (not Google)
- Severe rate limits (~200 queries before 1-hour cooldowns)
- Costs $8-10 per sweep vs $0 for SearXNG + NIM

The NIM pipeline (SearXNG + reranker + trafilatura + K2.5) replaces both the search and extraction components. Kimi deep search remains available as a standalone tool for manual sweeps but is being phased out of the automated pipeline.

---

## Model Routing Summary

| Task | Model | Cost |
|------|-------|------|
| **Writing** (briefing, market commentary, microscope, pre-event, executive summary) | Claude Opus 4.6 | ~$120/yr |
| **Macro/industry/province analysis** (Calls 1-3) | Claude Opus 4.6 | Included above |
| **Project extraction** (Call 4) | Claude Sonnet 4.6 | ~$30/yr |
| **Gap analysis, dedup QA, extraction recovery** | Claude Sonnet 4.6 | Included above |
| **Policy impact assessment** | Claude Sonnet 4.6 | Included above |
| **RSS article classification** (Layer 6, hundreds/week) | Gemini 2.5 Flash | $0 |
| **RSS article classification** (local fallback) | Qwen 2.5 3B (Ollama) | $0 |
| **Rehash detection, V-code search** | Gemini 2.5 Flash | $0 |
| **Deep search extraction** (discovery sweeps) | NIM K2.5 (thinking) | $0 |
| **Search result reranking** | NIM rerank-qa-mistral-4b | $0 |
| **Semantic dedup embeddings** | NIM nv-embedqa-e5-v5 | $0 |
| **PDF/image OCR** | NIM PaddleOCR | $0 |
| **Broad news discovery** (2,574 queries) | Google News RSS | $0 |
| **Targeted enrichment search** (1,000/month) | Tavily | $0 |
| **Unlimited web search** (deep sweeps) | SearXNG (self-hosted) | $0 |
| **Deep web search** (legacy, being phased out) | Moonshot v1-128k | ~$8-10/sweep |

---

## Design Principles

**1. Capability where it matters, free everywhere else.**
Opus writes the briefing. Sonnet does extraction and reasoning. Gemini Flash classifies articles. Qwen 2.5 handles it locally when available. Each step down in cost is a 5-25x savings per token with no quality loss on that specific task.

**2. Fail-open, not fail-closed.**
If the local LLM isn't running, fall back to Gemini Flash. If Gemini is rate-limited, pass all articles through. If Claude hits the cost cap, skip remaining calls gracefully. If SearXNG's Docker container is down, try a public instance. The pipeline always produces output, even in degraded mode.

**3. No grounding, no billing surprises.**
The $136/day Gemini grounding incident taught a hard lesson. The system now enforces at the code level that Gemini never receives grounding configuration. All web search goes through Google News RSS (free, unlimited) or SearXNG (self-hosted, unlimited) instead of through any pay-per-query search API.

**4. Hard budget enforcement.**
Claude has an $8/run cost cap enforced in code. Tavily has a 1,000 credit/month cap tracked in SQLite. NIM has a 40 RPM shared rate limit managed by a token bucket. Every paid or rate-limited API has a programmatic ceiling that cannot be exceeded by a bug or a prompt that generates too many calls.

**5. Every model is replaceable.**
Claude Opus could be swapped for any model with comparable prose quality. Sonnet could be replaced by any model that produces reliable structured JSON. Gemini Flash could be replaced by any free classification model. The local LLM is already a drop-in via Ollama — changing to a different model is a single environment variable. The architecture routes by task, not by vendor.
