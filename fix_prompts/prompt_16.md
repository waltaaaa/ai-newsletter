Run this with: `claude -p "$(cat fix_prompts/prompt_16.md)" --dangerously-skip-permissions --max-turns 50 --verbose`

---

I need you to add corporate press release monitoring via newswire RSS feeds. When a mining company announces a feasibility study or a REIT announces a new development, it shows up on newswires before it hits the news cycle. Read the relevant files before making changes.

## Context

Corporate press releases are primary sources — they're the company's own announcement of project milestones: feasibility studies, construction starts, cost updates, completion dates, partnership announcements. Your RSS infrastructure already handles this exact pattern. The newswires just need to be added as feeds and routed through the existing 6-layer filter.

## Part 1: Add newswire feeds to `rss_feeds.json`

Add the following feeds to `rss_feeds.json`. These should be tagged with `"type": "corporate_newswire"` so the metadata tagger (Prompt 12) can identify them:

```json
[
    {
        "name": "GlobeNewswire - Mining",
        "url": "https://www.globenewswire.com/RssFeed/subjectcode/15-Mining/feedTitle/GlobeNewswire - Mining",
        "type": "corporate_newswire",
        "sector": "mining",
        "enabled": true
    },
    {
        "name": "GlobeNewswire - Energy",
        "url": "https://www.globenewswire.com/RssFeed/subjectcode/36-Energy/feedTitle/GlobeNewswire - Energy",
        "type": "corporate_newswire",
        "sector": "oil_gas",
        "enabled": true
    },
    {
        "name": "GlobeNewswire - Real Estate",
        "url": "https://www.globenewswire.com/RssFeed/subjectcode/42-Real Estate/feedTitle/GlobeNewswire - Real Estate",
        "type": "corporate_newswire",
        "sector": "residential",
        "enabled": true
    },
    {
        "name": "GlobeNewswire - Construction",
        "url": "https://www.globenewswire.com/RssFeed/subjectcode/14-Construction/feedTitle/GlobeNewswire - Construction",
        "type": "corporate_newswire",
        "sector": "infrastructure",
        "enabled": true
    },
    {
        "name": "GlobeNewswire - Heavy Industry",
        "url": "https://www.globenewswire.com/RssFeed/subjectcode/39-Heavy Industry/feedTitle/GlobeNewswire - Heavy Industry",
        "type": "corporate_newswire",
        "sector": "manufacturing",
        "enabled": true
    },
    {
        "name": "Canada Newswire - Construction & Building",
        "url": "https://www.newswire.ca/rss/industry/construction-and-building-702.rss",
        "type": "corporate_newswire",
        "sector": "infrastructure",
        "enabled": true
    },
    {
        "name": "Canada Newswire - Mining & Metals",
        "url": "https://www.newswire.ca/rss/industry/mining-and-metals-720.rss",
        "type": "corporate_newswire",
        "sector": "mining",
        "enabled": true
    },
    {
        "name": "Canada Newswire - Energy & Utilities",
        "url": "https://www.newswire.ca/rss/industry/energy-and-utilities-706.rss",
        "type": "corporate_newswire",
        "sector": "oil_gas",
        "enabled": true
    },
    {
        "name": "Canada Newswire - Real Estate",
        "url": "https://www.newswire.ca/rss/industry/real-estate-730.rss",
        "type": "corporate_newswire",
        "sector": "residential",
        "enabled": true
    },
    {
        "name": "Canada Newswire - Transportation",
        "url": "https://www.newswire.ca/rss/industry/transportation-and-logistics-746.rss",
        "type": "corporate_newswire",
        "sector": "transport_logistics",
        "enabled": true
    },
    {
        "name": "Canada Newswire - Government",
        "url": "https://www.newswire.ca/rss/organization/government-762.rss",
        "type": "corporate_newswire",
        "sector": null,
        "enabled": true
    },
    {
        "name": "Cision - Canada Business",
        "url": "https://www.prnewswire.com/rss/news-releases-from-canada-list.rss",
        "type": "corporate_newswire",
        "sector": null,
        "enabled": true
    }
]
```

## Part 2: Update the metadata tagger domain map

File: `metadata_tagger.py` (from Prompt 12)

Add newswire domains to `DOMAIN_SECTOR_MAP`:

```python
# Newswire domains — sector comes from feed-level metadata, not domain
"globenewswire.com": [],  # Sector assigned by feed label
"newswire.ca": [],         # Sector assigned by feed label
"prnewswire.com": [],      # Sector assigned by feed label
```

These domains have empty sector lists because the sector comes from the feed-level `"sector"` field in `rss_feeds.json`, which the metadata tagger already handles via Signal 2 (feed-level metadata). The domain entry prevents them from being treated as unknown sources.

## Part 3: Add Canadian relevance filter for global newswires

File: `article_filter.py` or `rss_monitor.py`

GlobeNewswire and PRNewswire are global — many results will be US, European, or Asian companies. Add a Canadian relevance pre-filter for newswire feeds specifically:

```python
CANADIAN_INDICATORS = [
    # Company suffixes
    "ltd.", "inc.", "corp.", "limited",
    # Exchanges
    "tsx", "tsx-v", "cse",
    # Geography
    "canada", "canadian", "alberta", "ontario", "quebec", "british columbia",
    "saskatchewan", "manitoba", "nova scotia", "new brunswick",
    "newfoundland", "pei", "yukon", "nwt", "nunavut",
    # Cities (top 20 by project volume)
    "toronto", "vancouver", "calgary", "edmonton", "montreal",
    "ottawa", "winnipeg", "halifax", "saskatoon", "regina",
    "victoria", "hamilton", "kitchener", "london on",
    "st. john's", "moncton", "fredericton", "sudbury",
    # Canadian-specific terms
    "first nation", "indigenous", "crown land", "provincial",
]

def is_canadian_content(article):
    """Quick check if a newswire article is Canadian-relevant."""
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    return any(indicator in text for indicator in CANADIAN_INDICATORS)
```

Apply this filter to articles from feeds with `"type": "corporate_newswire"` before they enter the main 6-layer filter. Non-Canadian articles are dropped silently — they're not errors, just not relevant.

## Part 4: Update feed count in documentation

After adding feeds, update `CLAUDE.md` to reflect the new feed count. The current count (~201) will increase by 12. Update the RSS Feeds line in the Repository Layout and any references to feed count.

## Part 5: Update CLAUDE.md

Add to Discovery Pipeline section:
```
Corporate Newswires: 12 RSS feeds from GlobeNewswire, Canada Newswire, and Cision
covering mining, energy, real estate, construction, manufacturing, transport, and
government press releases. Pre-filtered for Canadian relevance before entering
the 6-layer RSS filter. Zero cost.
```

## Important constraints

- Zero cost — these are all public RSS feeds
- Newswire articles are CORPORATE PRESS RELEASES, not journalism. They're inherently promotional. The 6-layer filter handles this — L6 LLM classification catches puff pieces.
- The Canadian relevance filter must run BEFORE the main filter to avoid burning LLM classification tokens on US mining announcements
- GlobeNewswire RSS URLs may change subject codes over time. If a feed starts returning 404, the existing RSS monitor try/except handles it gracefully.
- These feeds are HIGH VOLUME. Expect 50-200 items per week across all 12 feeds. The 6-layer filter will reduce this to maybe 20-40 relevant items — which is the point.
- Do NOT add these feeds as a separate tier. They route through the existing Tier 4 RSS infrastructure.
