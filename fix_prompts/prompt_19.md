Run this with: `claude -p "$(cat fix_prompts/prompt_19.md)" --dangerously-skip-permissions --max-turns 50 --verbose`

---

I need you to add regulatory and court filing monitoring via CanLII RSS feeds. Environmental compliance orders, zoning appeals, and regulatory tribunal decisions signal project status changes that don't appear in news coverage. Read the relevant files before making changes.

## Context

A compliance order against a construction site confirms "under construction." A zoning appeal for a tower means the project is real but contested. A tribunal decision approving a pipeline route means the project cleared a major hurdle. These legal/regulatory signals are highly reliable — they're official government records — but they currently don't feed into the pipeline.

CanLII (Canadian Legal Information Institute) publishes RSS feeds by jurisdiction and topic. Environmental tribunals, municipal boards, energy regulators, and provincial courts all post decisions that directly affect tracked projects.

## Part 1: Add regulatory feeds to `rss_feeds.json`

Add the following feeds to `rss_feeds.json`. Tag them with `"type": "regulatory"` and `"source_type": "government"` so they get the government bypass in the RSS filter (L1):

```json
[
    {
        "name": "CanLII - Federal Court",
        "url": "https://www.canlii.org/en/ca/fct/rss.xml",
        "type": "regulatory",
        "source_type": "government",
        "sector": null,
        "enabled": true,
        "notes": "Federal Court decisions — environmental reviews, regulatory challenges"
    },
    {
        "name": "CanLII - National Energy Board / CER",
        "url": "https://www.canlii.org/en/ca/neb/rss.xml",
        "type": "regulatory",
        "source_type": "government",
        "sector": "oil_gas",
        "enabled": true,
        "notes": "CER pipeline and energy decisions"
    },
    {
        "name": "CanLII - Ontario Municipal Board / LPAT",
        "url": "https://www.canlii.org/en/on/onlpat/rss.xml",
        "type": "regulatory",
        "source_type": "government",
        "sector": null,
        "enabled": true,
        "notes": "Ontario Land Planning Appeal Tribunal — zoning, OMB successor"
    },
    {
        "name": "CanLII - Ontario Environmental Review Tribunal",
        "url": "https://www.canlii.org/en/on/onert/rss.xml",
        "type": "regulatory",
        "source_type": "government",
        "sector": null,
        "enabled": true,
        "notes": "Ontario environmental approvals and appeals"
    },
    {
        "name": "CanLII - BC Environmental Appeal Board",
        "url": "https://www.canlii.org/en/bc/bceab/rss.xml",
        "type": "regulatory",
        "source_type": "government",
        "sector": null,
        "enabled": true,
        "notes": "BC environmental permit appeals"
    },
    {
        "name": "CanLII - BC Utilities Commission",
        "url": "https://www.canlii.org/en/bc/bcuc/rss.xml",
        "type": "regulatory",
        "source_type": "government",
        "sector": "power_energy",
        "enabled": true,
        "notes": "BC energy and utility rate decisions"
    },
    {
        "name": "CanLII - Alberta Energy Regulator",
        "url": "https://www.canlii.org/en/ab/abaer/rss.xml",
        "type": "regulatory",
        "source_type": "government",
        "sector": "oil_gas",
        "enabled": true,
        "notes": "Alberta energy project approvals and compliance"
    },
    {
        "name": "CanLII - Alberta Utilities Commission",
        "url": "https://www.canlii.org/en/ab/abauc/rss.xml",
        "type": "regulatory",
        "source_type": "government",
        "sector": "power_energy",
        "enabled": true,
        "notes": "Alberta power generation and transmission decisions"
    },
    {
        "name": "CanLII - Quebec Environmental Tribunal",
        "url": "https://www.canlii.org/fr/qc/qctaq/rss.xml",
        "type": "regulatory",
        "source_type": "government",
        "sector": null,
        "enabled": true,
        "notes": "Quebec TAQ environmental decisions (French)"
    },
    {
        "name": "CanLII - Saskatchewan Assessment Appeals",
        "url": "https://www.canlii.org/en/sk/sksmb/rss.xml",
        "type": "regulatory",
        "source_type": "government",
        "sector": null,
        "enabled": true,
        "notes": "SK Municipal Board — assessment and planning appeals"
    }
]
```

## Part 2: Create a regulatory relevance filter

File: `article_filter.py` or create a lightweight filter function

CanLII feeds include many decisions unrelated to capital projects (family law, criminal, etc.). Add a keyword filter that runs on regulatory feeds before they enter the main pipeline:

```python
REGULATORY_KEYWORDS = [
    # Project types
    "construction", "development", "building permit", "site plan",
    "zoning", "official plan", "subdivision", "rezoning",
    "environmental assessment", "environmental approval",
    "compliance order", "remediation order", "stop work",
    
    # Infrastructure
    "pipeline", "transmission line", "generating station", "wind farm",
    "solar", "refinery", "mine", "quarry", "port", "terminal",
    "highway", "bridge", "water treatment", "wastewater",
    
    # Regulatory actions
    "approved", "denied", "dismissed", "granted", "suspended",
    "variance", "amendment", "certificate of approval",
    "licence", "license", "permit",
    
    # Parties (project proponents)
    "proponent", "applicant", "developer", "operator",
]

def is_regulatory_relevant(article):
    """Filter CanLII/regulatory feed items for project relevance."""
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    matches = sum(1 for kw in REGULATORY_KEYWORDS if kw in text)
    return matches >= 2  # Require at least 2 keyword matches
```

Apply this to articles from feeds tagged `"type": "regulatory"` before they enter the main 6-layer filter. Items that fail this pre-filter are dropped — they're not project-related legal decisions.

## Part 3: Regulatory status signal extraction

These regulatory decisions carry specific status signals. Add logic to detect them:

```python
REGULATORY_STATUS_SIGNALS = {
    # Positive progression
    "approved": "Approved",
    "granted": "Approved",
    "certificate of approval": "Approved",
    "licence issued": "Approved",
    "permit issued": "Approved",
    
    # Negative / blocking
    "denied": "On Hold",
    "dismissed": None,  # Appeal dismissed — status unchanged
    "suspended": "Suspended",
    "stop work order": "On Hold",
    "compliance order": "Under Construction",  # Confirms active construction
    "remediation order": "Under Construction",  # Confirms site activity
    
    # Cancelled
    "revoked": "Cancelled",
    "withdrawn": "Cancelled",
}

def extract_regulatory_signal(article):
    """Extract project status signal from a regulatory decision."""
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    
    for keyword, status in REGULATORY_STATUS_SIGNALS.items():
        if keyword in text:
            return {
                "signal": keyword,
                "implied_status": status,
                "source": article.get("url", ""),
                "title": article.get("title", ""),
            }
    return None
```

Pass extracted signals to the analysis phase so Claude can incorporate them.

## Part 4: Update documentation

Update `CLAUDE.md` feed count to include the 10 new regulatory feeds.

Add to Discovery section:
```
Regulatory Feeds: 10 CanLII RSS feeds covering Federal Court, CER, Ontario LPAT,
Ontario/BC/Alberta environmental tribunals, BC/Alberta utilities commissions, 
Quebec TAQ, and Saskatchewan Municipal Board. Pre-filtered for project relevance
(≥2 keyword matches). Regulatory decisions carry status signals: approvals, 
denials, compliance orders, and stop-work orders map to project status updates.
Tagged as government sources — bypass RSS keyword filter (L1). Zero cost.
```

## Important constraints

- Zero cost — CanLII RSS feeds are free public data
- Tag regulatory feeds as `"source_type": "government"` so they get the L1 government bypass in the RSS filter. Regulatory decisions are authoritative sources.
- The 2-keyword relevance filter is intentionally loose — better to let some irrelevant legal decisions through to the LLM filter than to miss a pipeline approval.
- Quebec TAQ feed is in French. The keyword matching still works for technical terms (pipeline, construction, etc.) but may miss some French-only terms. This is acceptable — it catches the major project decisions.
- CanLII RSS feeds have variable update frequency. Some tribunals post daily, others weekly. This is fine for a weekly pipeline.
- Compliance orders and remediation orders are POSITIVE signals for the database — they confirm that a project site is active, even though the legal context is negative (violation). Map these to "Under Construction" status.
- Do NOT add these as a new numbered tier. Route them through existing Tier 4 RSS infrastructure.
