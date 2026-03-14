Run this with: `claude -p "$(cat fix_prompts/prompt_20.md)" --dangerously-skip-permissions --max-turns 50 --verbose`

---

I need you to wire all the new data streams from Prompts 11-19 into the narrative and analysis phases so they inform the weekly briefing, Under the Microscope, market commentary, and provincial spotlight. Without this step, the new data is collected but never surfaces in the written output. Read the relevant files before making changes.

## Context

After Prompts 11-19, the pipeline collects these new signals:
- **Snippet enhancement** (Prompt 11) — better article text for classification
- **Metadata tags** (Prompt 12) — sector/province pre-classification on articles
- **Job postings** (Prompt 13) — hiring spikes by employer/CMA/sector
- **Procurement** (Prompt 14) — government contract awards and tenders ≥$5M
- **Policy tracker** (Prompt 15) — legislative and regulatory developments with project linkages
- **Corporate newswires** (Prompt 16) — press releases routed through RSS filter
- **Extended StatCan** (Prompt 17) — investment, employment, trade, housing indicators
- **IAAC status** (Prompt 18) — assessment status changes on federal projects
- **Regulatory filings** (Prompt 19) — tribunal/court decisions with status signals

Most of these feed into the context dict during earlier phases. The narrative phase needs to pull them out and include them in the Claude analysis prompts so the written output reflects the full picture.

## Part 1: Update Claude Call 1 — Executive Summary and National Analysis

File: `phases/analysis.py` or `claude_reasoning.py`

Claude Call 1 produces the executive summary, national analysis, global vectors, and consumer pulse. Add the following to its input payload:

```python
# Add to the data payload for Claude Call 1
call1_payload["policy_developments"] = context.get("policy_summary", {})
call1_payload["hiring_spikes"] = context.get("job_spikes", [])[:10]
call1_payload["procurement_highlights"] = [
    {
        "source": c["source"],
        "description": c.get("description", c.get("title", "")),
        "value": c.get("value"),
        "province": c.get("province"),
        "linked_projects": c.get("linked_projects", [])[:3],
    }
    for c in context.get("procurement_contracts", [])[:10]
    if c.get("value", 0) >= 10_000_000  # Only include $10M+ for the summary
]
call1_payload["iaac_status_changes"] = context.get("iaac_status_changes", [])
call1_payload["extended_indicators"] = {
    "statcan_tables_fetched": context.get("statcan_extended_tables", 0),
    "new_indicators_saved": context.get("statcan_extended_saved", 0),
}
```

Update the Claude Call 1 system prompt to reference these new inputs:

```
Add to the existing system prompt (do NOT replace — append):

Additional data available this week:

POLICY DEVELOPMENTS: {policy_developments}
Legislative and regulatory changes affecting capital investment. For each item,
note the affected sectors and number of projects in scope. Report what happened
factually — do not predict outcomes or recommend responses.

HIRING SIGNALS: {hiring_spikes}
Employer hiring spikes detected from job posting monitoring. A spike indicates
a company is mobilizing — possible project status change from proposed to active.
Reference specific employers and locations.

GOVERNMENT PROCUREMENT: {procurement_highlights}
Federal and provincial contract awards and tenders ≥$10M in construction and
infrastructure. Awards confirm project advancement. Link to tracked projects
where matched.

ASSESSMENT STATUS CHANGES: {iaac_status_changes}
Federal impact assessment status transitions. Note any projects that advanced
or were terminated/withdrawn.
```

## Part 2: Update Claude Call 2 — Industry Analysis

File: `phases/analysis.py` or `claude_reasoning.py`

Claude Call 2 produces industry analysis for 5 goods + 15 services sectors. Add sector-specific context from the new data:

```python
# Build per-sector context from new data streams
sector_context = {}

# Policy items by affected sector
for item in context.get("policy_items", []):
    for sector in item.get("affected_sectors", []):
        if sector not in sector_context:
            sector_context[sector] = {"policy": [], "hiring": [], "procurement": []}
        sector_context[sector]["policy"].append({
            "title": item["title"],
            "source_type": item["source_type"],
            "affected_projects_total": item.get("affected_projects_total", 0),
            "affected_projects_value": item.get("affected_projects_value", 0),
        })

# Hiring spikes by sector
for spike in context.get("job_spikes", []):
    sector = spike.get("sector")
    if sector:
        if sector not in sector_context:
            sector_context[sector] = {"policy": [], "hiring": [], "procurement": []}
        sector_context[sector]["hiring"].append({
            "employer": spike["employer"],
            "location": spike["location"],
            "count": spike["current_count"],
            "multiplier": spike["multiplier"],
        })

# Procurement by sector (inferred from linked projects)
for contract in context.get("procurement_contracts", []):
    for project in contract.get("linked_projects", []):
        sector = project.get("sector")
        if sector:
            if sector not in sector_context:
                sector_context[sector] = {"policy": [], "hiring": [], "procurement": []}
            sector_context[sector]["procurement"].append({
                "description": contract.get("description", "")[:200],
                "value": contract.get("value"),
                "vendor": contract.get("vendor", ""),
            })

call2_payload["sector_signals"] = sector_context
```

Update the Call 2 system prompt:

```
Add to the existing system prompt:

SECTOR SIGNALS: {sector_signals}
For each sector, you may have additional context:
- policy: Legislative/regulatory developments affecting this sector
- hiring: Employer hiring spikes in this sector's workforce
- procurement: Government contract awards linked to projects in this sector

Incorporate these signals into the sector analysis where relevant. State facts:
"3 hiring spikes detected in Alberta oil & gas" — not opinions about what they mean.
```

## Part 3: Update Claude Call 3 — Provincial Analysis

File: `phases/analysis.py` or `claude_reasoning.py`

Claude Call 3 produces analysis for all 13 provinces. Add province-specific context:

```python
# Build per-province context
province_context = {}

# Policy items by province
for item in context.get("policy_items", []):
    prov = item.get("province")
    if prov:
        if prov not in province_context:
            province_context[prov] = {"policy": [], "hiring": [], "procurement": [],
                                       "iaac_changes": []}
        province_context[prov]["policy"].append({
            "title": item["title"],
            "categories": item["policy_categories"],
        })

# Hiring spikes by province (via CMA → province mapping)
for spike in context.get("job_spikes", []):
    # The job_monitor includes province in spike data
    prov = _cma_to_province(spike.get("location", ""))
    if prov:
        if prov not in province_context:
            province_context[prov] = {"policy": [], "hiring": [], "procurement": [],
                                       "iaac_changes": []}
        province_context[prov]["hiring"].append({
            "employer": spike["employer"],
            "location": spike["location"],
            "sector": spike["sector"],
            "count": spike["current_count"],
        })

# Procurement by province
for contract in context.get("procurement_contracts", []):
    prov = contract.get("province")
    if prov:
        if prov not in province_context:
            province_context[prov] = {"policy": [], "hiring": [], "procurement": [],
                                       "iaac_changes": []}
        province_context[prov]["procurement"].append({
            "description": contract.get("description", "")[:200],
            "value": contract.get("value"),
        })

# IAAC status changes by province
for change in context.get("iaac_status_changes", []):
    prov = change.get("province")
    if prov:
        if prov not in province_context:
            province_context[prov] = {"policy": [], "hiring": [], "procurement": [],
                                       "iaac_changes": []}
        province_context[prov]["iaac_changes"].append({
            "project": change["project_name"],
            "old_status": change["old_status"],
            "new_status": change["new_status"],
        })

call3_payload["province_signals"] = province_context
```

## Part 4: Update Weekly Briefing prompt

File: `weekly_briefing.py`

The weekly briefing (8 sections) should incorporate the new signals. Update the briefing data payload:

```python
briefing_data["policy_summary"] = context.get("policy_summary", {})
briefing_data["hiring_spikes"] = context.get("job_spikes", [])[:5]  # Top 5 only
briefing_data["procurement_awards"] = [
    c for c in context.get("procurement_contracts", [])
    if c.get("value", 0) >= 10_000_000
][:5]
briefing_data["iaac_changes"] = context.get("iaac_status_changes", [])
briefing_data["regulatory_signals"] = [
    # Extract from articles tagged as regulatory with status signals
    a for a in context.get("discovered_articles", [])
    if a.get("regulatory_signal")
][:5]
```

Update the briefing system prompt to tell Claude how to use these:

```
Add to the existing briefing system prompt:

ADDITIONAL DATA SOURCES THIS WEEK:

POLICY TRACKER: {policy_summary}
Include significant policy developments in the relevant briefing sections:
- New legislation affecting housing → Section 1 (Headline) if major, or Section 5 (Sector Watch)
- Federal budget items → Section 2 (Macro Pulse)
- Provincial policy → Section 4 (Provincial Spotlight) if the featured province is affected
- Trade policy → Section 7 (Markets & Commodities) if it affects commodity trade
- Upcoming regulatory deadlines → Section 8 (Looking Ahead)
Report what happened and how many projects are in scope. No predictions.

HIRING SIGNALS: {hiring_spikes}
Hiring spikes indicate project mobilization. Include in:
- Section 6 (Project Tracker) — "Hiring spike at [employer] in [location] suggests [project] is mobilizing"
- Section 4 (Provincial Spotlight) if concentrated in the featured province

PROCUREMENT AWARDS: {procurement_awards}
Government contract awards confirm project advancement. Include in:
- Section 6 (Project Tracker) — "[Department] awarded $[value] to [vendor] for [description]"
- Section 5 (Sector Watch) if concentrated in a specific sector

ASSESSMENT STATUS CHANGES: {iaac_changes}
Federal assessment transitions. Include in:
- Section 6 (Project Tracker) — "[Project] advanced from [old] to [new] in IAAC assessment"

REGULATORY DECISIONS: {regulatory_signals}
Tribunal and court decisions. Include in:
- Section 6 (Project Tracker) — "[Tribunal] [approved/denied] [project]"

IMPORTANT: All new data sources follow the same editorial rules as everything else.
State what happened, cite the source, reference specific numbers and project names.
No predictions, no "good news/bad news" framing, no recommendations.
```

## Part 5: Update Under the Microscope topic selection

File: `under_the_microscope.py`

The topic selection algorithm should consider new data when picking the week's deep-dive topic. A sector with simultaneous policy changes, hiring spikes, and procurement awards is a stronger candidate than one with only project volume changes.

Add a scoring boost for topics with multi-signal convergence:

```python
def calculate_topic_score(sector, context):
    """Enhanced topic scoring with new data signals."""
    score = base_score  # existing scoring logic
    
    # Boost for policy convergence
    policy_items = [p for p in context.get("policy_items", []) 
                    if sector in p.get("affected_sectors", [])]
    if policy_items:
        score += len(policy_items) * 2  # Each policy item adds weight
    
    # Boost for hiring activity
    hiring_spikes = [s for s in context.get("job_spikes", [])
                     if s.get("sector") == sector]
    if hiring_spikes:
        score += len(hiring_spikes) * 3  # Hiring spikes are strong signals
    
    # Boost for procurement activity
    procurement = [c for c in context.get("procurement_contracts", [])
                   if any(p.get("sector") == sector 
                          for p in c.get("linked_projects", []))]
    if procurement:
        score += len(procurement) * 2
    
    # Boost for IAAC status changes
    iaac_changes = [c for c in context.get("iaac_status_changes", [])
                    if c.get("sector") == sector]
    if iaac_changes:
        score += len(iaac_changes) * 4  # Assessment changes are major events
    
    return score
```

## Part 6: Update Market Commentary

File: `canadian_markets.py`

The market commentary should reference trade policy developments from the policy tracker when discussing commodity prices:

```python
# Add to the market commentary data payload
market_data["trade_policy"] = [
    p for p in context.get("policy_items", [])
    if "trade_policy" in p.get("policy_categories", [])
]
market_data["export_indicators"] = [
    # Pull from extended StatCan indicators if available
    i for i in context.get("new_indicators", [])
    if "export" in i.get("indicator", "").lower()
]
```

Update the market commentary prompt:
```
Add: If trade policy developments (tariffs, export controls, trade agreements) occurred
this week, note them alongside affected commodity price movements and the number of 
projects in affected sectors. State the policy change and the data — do not speculate
on impact.
```

## Part 7: Create `policy.json` export

File: `export_dashboard.py`

Prompt 10 Fix 1 identified that the frontend references `policy.json` but it's never created. Now that we have the policy tracker, create this export:

```python
def export_policy_json(conn, output_dir):
    """Export policy developments for the frontend."""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT week_of, summary FROM policy_snapshots
            ORDER BY week_of DESC LIMIT 8
        """)
        rows = cursor.fetchall()
        
        policy_data = {
            "weeks": [
                {"week_of": row[0], "summary": json.loads(row[1])}
                for row in rows
            ],
            "last_updated": datetime.now().isoformat(),
        }
        
        output_path = os.path.join(output_dir, "policy.json")
        with open(output_path, "w") as f:
            json.dump(policy_data, f, indent=2)
        
        print(f"[EXPORT] policy.json: {len(rows)} weeks of policy data")
    except Exception as e:
        print(f"[WARN] policy.json export failed: {e}")
```

Call this from the export phase alongside the other JSON exports.

## Part 8: Create `commodities.json` export

File: `export_dashboard.py`

The frontend also references `commodities.json`. Now that we have extended StatCan trade data and existing commodity timeseries, create this export:

```python
def export_commodities_json(conn, output_dir):
    """Export commodity data for the frontend."""
    cursor = conn.cursor()
    
    try:
        # Pull from timeseries table (existing) + extended trade indicators (new)
        cursor.execute("""
            SELECT name, date, value FROM timeseries
            WHERE name IN ('WTI', 'WCS', 'Natural Gas', 'Gold', 'Copper', 
                           'Lumber', 'Potash', 'Uranium', 'Nickel')
            ORDER BY name, date DESC
        """)
        rows = cursor.fetchall()
        
        commodities = {}
        for name, date, value in rows:
            if name not in commodities:
                commodities[name] = []
            commodities[name].append({"date": date, "value": value})
        
        output_path = os.path.join(output_dir, "commodities.json")
        with open(output_path, "w") as f:
            json.dump({
                "commodities": commodities,
                "last_updated": datetime.now().isoformat(),
            }, f, indent=2)
        
        print(f"[EXPORT] commodities.json: {len(commodities)} commodities")
    except Exception as e:
        print(f"[WARN] commodities.json export failed: {e}")
```

## Part 9: Update CLAUDE.md

Update the Weekly Briefing Structure section to note the additional data sources:

```
The briefing integrates data from: indicator history, project database, discovery 
articles, policy tracker (legislative/regulatory developments), job monitor 
(hiring spikes), procurement monitor (contract awards), IAAC status changes, 
and regulatory tribunal decisions. All sources cited factually per editorial policy.
```

Update the Claude Analysis Calls table to note the expanded payloads:

```
| Call | Additional Context (from Prompts 11-19) |
|------|------------------------------------------|
| 1    | Policy summary, top hiring spikes, procurement ≥$10M, IAAC changes |
| 2    | Per-sector signals: policy, hiring, procurement |
| 3    | Per-province signals: policy, hiring, procurement, IAAC changes |
```

## Important constraints

- All additions to Claude prompts are FACTUAL framing. "3 hiring spikes detected" not "the sector is heating up."
- New data is ADDITIVE to the existing prompt — do not remove or replace any existing context. Append new sections.
- Keep the new context concise. Top 5-10 items per signal type. Claude's context window is limited and the existing data already fills most of it.
- The policy.json and commodities.json exports resolve Prompt 10 Fix 1. If Prompt 10 already handled this with option (b) (removing frontend references), switch to option (a) now that the data exists.
- Under the Microscope topic scoring is a SUGGESTION — review the weights and adjust after seeing a few weeks of output. The hiring spike weight (3) and IAAC change weight (4) may need tuning.
- All editorial rules apply to the new data exactly as they do to existing data. No exceptions.
