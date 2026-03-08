"""
google_alerts.py — Google Alerts RSS feed integration.

Google Alerts can deliver as RSS feeds instead of email. Each alert becomes
a standard RSS URL that plugs directly into the existing feed pipeline.

Setup (one-time manual):
  1. Go to https://google.com/alerts
  2. Create each alert with "Deliver to: RSS feed"
  3. Copy the RSS URL (format: https://www.google.com/alerts/feeds/XXXX/YYYY)
  4. Paste into GOOGLE_ALERT_FEEDS below or rss_feeds.json

This module provides:
  - Recommended alert search terms for Canadian infrastructure monitoring
  - Feed config generation for rss_feeds.json integration
  - Helper to validate alert RSS feeds are active
"""

import logging
import feedparser
import requests

logger = logging.getLogger(__name__)

# ── Recommended Google Alerts (create manually at google.com/alerts) ──────
# Set each to: Sources=News+Web, Language=English, Region=Canada, Deliver=RSS

RECOMMENDED_ALERTS = {
    # High-value catch-all
    "billion_project_ca": '"billion dollar" project Canada construction',
    "hundred_million_ca": '"hundred million" project Canada construction',
    "major_project_approved": '"major project" approved Canada',
    "construction_begins": '"construction begins" Canada million',

    # Brownfield / adaptive reuse
    "redevelopment_ca": '"redevelopment" million Canada project',
    "adaptive_reuse_ca": '"adaptive reuse" Canada project',
    "conversion_residential": '"conversion" residential Canada project',
    "revitalization_ca": '"revitalization" Canada million',

    # Sector-specific
    "mine_approved_ca": '"mine" approved Canada',
    "pipeline_approved": '"pipeline" approved Canada',
    "lng_project_ca": '"LNG" project Canada',
    "data_centre_ca": '"data centre" Canada construction',
    "battery_plant_ca": '"battery plant" Canada',
    "smr_ca": '"SMR" "small modular reactor" Canada',
    "transit_extension": '"transit" extension Canada approved',
    "hospital_construction": '"hospital" construction Canada million',
    "affordable_housing": '"affordable housing" construction Canada million',

    # French
    "projet_majeur_qc": '"projet majeur" construction Canada million',
    "reamenagement_qc": '"réaménagement" Québec million',
    "construction_qc": '"construction" approuvé Québec million',

    # Status changes
    "project_delayed": '"project delayed" Canada construction',
    "cost_overrun": '"cost overrun" Canada project',
    "project_cancelled": '"project cancelled" Canada construction',
}

# ── Active alert RSS feeds (paste URLs here after creating alerts) ────────
# Format: id -> RSS URL
# When you create an alert with RSS delivery, Google gives you a URL like:
#   https://www.google.com/alerts/feeds/01234567890123456789012/1234567890123456789012
#
# Paste those URLs here:

GOOGLE_ALERT_FEEDS: dict[str, dict] = {
    # Example (replace with your actual feed URLs):
    # "ga_billion_project": {
    #     "name": "Google Alert: Billion-dollar projects Canada",
    #     "url": "https://www.google.com/alerts/feeds/XXXX/YYYY",
    #     "source_type": "google_alert",
    #     "priority": 2,
    #     "enabled": True,
    # },
}


def get_alert_feed_config() -> list[dict]:
    """Return active Google Alert feeds in rss_feeds.json format.

    These can be added to the 'industry' category in rss_feeds.json
    or loaded directly by rss_monitor.py.
    """
    feeds = []
    for feed_id, feed in GOOGLE_ALERT_FEEDS.items():
        if not feed.get("enabled", True):
            continue
        if not feed.get("url"):
            continue
        feeds.append({
            "id": feed_id,
            "name": feed.get("name", feed_id),
            "url": feed["url"],
            "source_type": "google_alert",
            "jurisdiction": None,
            "province_map": None,
            "priority": feed.get("priority", 2),
            "enabled": True,
        })
    return feeds


def test_alert_feeds() -> dict[str, bool]:
    """Test which Google Alert RSS feeds are active and returning results."""
    results = {}
    for feed_id, feed in GOOGLE_ALERT_FEEDS.items():
        url = feed.get("url", "")
        if not url:
            results[feed_id] = False
            continue
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                parsed = feedparser.parse(resp.content)
                results[feed_id] = len(parsed.entries) > 0
            else:
                results[feed_id] = False
        except Exception:
            results[feed_id] = False

    active = sum(1 for v in results.values() if v)
    logger.info(f"Google Alerts: {active}/{len(results)} feeds active")
    return results


def print_setup_instructions():
    """Print step-by-step instructions for setting up Google Alerts."""
    print("\n" + "=" * 66)
    print("  GOOGLE ALERTS SETUP INSTRUCTIONS")
    print("=" * 66)
    print()
    print("1. Go to https://google.com/alerts")
    print("2. For EACH alert below, create it with these settings:")
    print("   - How often: As-it-happens")
    print("   - Sources: News")
    print("   - Language: English (French for QC alerts)")
    print("   - Region: Canada")
    print("   - How many: All results")
    print("   - Deliver to: RSS feed")
    print()
    print("3. After creating each alert, click the RSS icon to get the feed URL")
    print("4. Paste the URL into GOOGLE_ALERT_FEEDS in google_alerts.py")
    print()
    print("Recommended alerts to create:")
    print("-" * 50)
    for alert_id, query in RECOMMENDED_ALERTS.items():
        print(f"  {alert_id}: {query}")
    print()
    print(f"Total: {len(RECOMMENDED_ALERTS)} alerts "
          f"(limit: ~30 per Google account)")
    print("=" * 66)
