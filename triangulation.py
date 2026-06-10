"""
triangulation.py — Map evidence entries / discovery sources to 5 triangulation axes.

G8 (quality-pass-1.4). A project's claims are better corroborated when they are
observed through structurally independent channels, not just multiple media
articles. Each observation (evidence entry or discovery-source tag) maps to
exactly one axis:

  regulatory           — IAAC, provincial EA registries, CER, regulatory tribunal
                         feeds, government registry domains
  financial_disclosure — SEDAR filings, corporate IR, corporate newswires
  commercial           — procurement awards/tenders, municipal development
                         applications, building permits
  pre_public           — lobbyist registries, key-people tracking, corporate
                         watchlist / newsroom diffs
  media                — everything else (Google News, RSS, Bing, aggregators)

`axes_satisfied(evidence, discovery_sources)` returns the count of distinct
axes with at least one observation (0-5). Persisted on projects.axes_satisfied
by db.upsert_project.

Zero cost, no I/O, purely deterministic.
"""

AXES = ("regulatory", "financial_disclosure", "commercial", "pre_public", "media")

# Substring tokens checked IN ORDER against source identifier strings
# (discovery_source tags, evidence 'source'/'source_type' fields).
# pre_public is checked first so 'lobbyist_registries' does not fall into
# regulatory via its 'registr' substring.
_AXIS_TOKENS = (
    ("pre_public", (
        "lobbyist", "key_people", "watchlist", "newsroom",
    )),
    ("financial_disclosure", (
        "sedar", "corporate_ir", "company_ir", "newswire", "securities",
    )),
    ("commercial", (
        "procurement", "buyandsell", "canadabuys", "municipal", "permit",
        "tender", "bcbid", "bps",
    )),
    ("regulatory", (
        "iaac", "provincial_ea", "cer_registry", "cer-rec", "regulatory",
        "ero", "eao", "federal_registry", "provincial_registry", "gov_api",
        "crown_corp", "infrastructure_canada", "nrcan", "cib", "registry",
        "gov_newsroom", "rss_gov", "gazette", "tribunal",
    )),
)


def classify_axis(source: str = "", url: str = "") -> str:
    """Classify one observation into a triangulation axis.

    Args:
        source: a discovery-source tag or evidence source/source_type string
                (e.g. 'iaac_registry', 'sedar_filings', 'google_news_rss').
        url:    optional source URL — government domains map to 'regulatory',
                SEDAR domains to 'financial_disclosure'.

    Returns: one of AXES; defaults to 'media'.
    """
    s = (source or "").strip().lower()
    if s:
        for axis, tokens in _AXIS_TOKENS:
            if any(t in s for t in tokens):
                return axis

    if url:
        u = url.lower()
        if "sedarplus.ca" in u or "sedar.com" in u:
            return "financial_disclosure"
        try:
            from url_utils import classify_source_authority
            if classify_source_authority(url) == "government":
                return "regulatory"
        except Exception:
            pass

    return "media"


def _evidence_axis(entry) -> str:
    """Classify a single projects.evidence JSON entry (dict or bare URL string)."""
    if isinstance(entry, str):
        return classify_axis("", entry)
    if not isinstance(entry, dict):
        return "media"
    # authority field is stamped at build time by project_schema/url_utils
    if entry.get("authority") == "government":
        return "regulatory"
    source = entry.get("source") or entry.get("source_type") or ""
    return classify_axis(source, entry.get("url", ""))


def axes_satisfied(evidence: list, discovery_sources: list) -> int:
    """Count distinct triangulation axes with >=1 observation.

    Args:
        evidence: projects.evidence JSON array (list of dicts or URL strings).
        discovery_sources: list of discovery-source tag strings.

    Returns: int 0-5.
    """
    seen = set()
    for entry in (evidence or []):
        seen.add(_evidence_axis(entry))
    for src in (discovery_sources or []):
        if isinstance(src, str) and src.strip():
            seen.add(classify_axis(src))
    return len(seen & set(AXES))
