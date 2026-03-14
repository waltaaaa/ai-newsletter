"""
archetype_audit.py — Scan rejected articles for emerging archetype patterns.

Run monthly or quarterly via: python update_dashboard.py --audit-archetypes

Requires the `documents` table (from Phase 4) to be populated with rejection data.
Identifies clusters of rejected articles that share vocabulary, suggesting
project types the pipeline doesn't yet recognize.
"""

import re
from collections import Counter

# Canadian provinces and CMAs for geographic filtering
_CANADIAN_LOCATIONS = {
    'ontario', 'quebec', 'alberta', 'british columbia', 'manitoba',
    'saskatchewan', 'nova scotia', 'new brunswick', 'newfoundland',
    'labrador', 'prince edward island', 'yukon', 'northwest territories',
    'nunavut', 'toronto', 'montreal', 'vancouver', 'calgary', 'edmonton',
    'ottawa', 'winnipeg', 'quebec city', 'hamilton', 'kitchener',
    'london', 'victoria', 'halifax', 'oshawa', 'windsor', 'saskatoon',
    'regina', 'st. john', 'barrie', 'kelowna', 'abbotsford', 'sudbury',
    'thunder bay', 'moncton', 'fredericton', 'charlottetown', 'whitehorse',
    'yellowknife', 'iqaluit', 'canada', 'canadian',
}


def _mentions_canadian_location(text):
    """Check if text mentions a Canadian province or CMA."""
    text_lower = text.lower()
    return any(loc in text_lower for loc in _CANADIAN_LOCATIONS)


def _extract_noun_phrases(text):
    """Extract 2-3 word capitalized phrases as candidate noun phrases.

    Simple regex approach — no NLP dependency needed.
    """
    # Match sequences of 2-3 capitalized words
    phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Za-z]+){1,2}\b', text)
    # Filter out very short phrases and common non-project phrases
    _SKIP = {
        'The Canadian', 'Prime Minister', 'United States', 'New York',
        'North America', 'South America', 'Bank Of', 'Bank of Canada',
        'Statistics Canada', 'Government Of', 'City Of', 'Province Of',
        'University Of', 'Department Of', 'Ministry Of', 'Office Of',
    }
    return [p for p in set(phrases) if len(p) > 5 and p not in _SKIP]


def _load_existing_keywords():
    """Load existing Cat A project keywords from article_filter.py."""
    try:
        from article_filter import _CAT_A
        if isinstance(_CAT_A, (list, set, tuple)):
            return {kw.lower() for kw in _CAT_A}
        # If _CAT_A is a dict of lists
        keywords = set()
        if isinstance(_CAT_A, dict):
            for v in _CAT_A.values():
                if isinstance(v, (list, set, tuple)):
                    for kw in v:
                        keywords.add(str(kw).lower())
        return keywords
    except (ImportError, AttributeError):
        return set()


def audit_rejected_articles(conn, days=30, min_cluster_size=5):
    """Scan rejected articles for emerging archetype patterns.

    Args:
        conn: sqlite3.Connection from db.py
        days: look back N days
        min_cluster_size: minimum articles sharing a phrase to flag

    Returns:
        list of emerging archetype dicts with phrase, count, examples, suggestion
    """
    try:
        rejected = conn.execute("""
            SELECT url, title, classification_json
            FROM documents
            WHERE is_relevant = 0
            AND fetch_date >= date('now', ? || ' days')
        """, (f'-{days}',)).fetchall()
    except Exception as e:
        print(f"  [ARCHETYPE] Error querying documents table: {e}")
        return []

    if not rejected:
        print(f"  [ARCHETYPE] No rejected articles in last {days} days")
        return []

    # Filter to Canadian-mentioning articles
    canadian_rejected = [
        dict(r) for r in rejected
        if _mentions_canadian_location(r['title'] or '')
    ]

    if not canadian_rejected:
        print(f"  [ARCHETYPE] {len(rejected)} rejected articles, "
              f"none mention Canadian locations")
        return []

    # Extract noun phrases
    phrase_counts = Counter()
    article_phrases = {}
    for article in canadian_rejected:
        text = article.get('title') or ''
        phrases = _extract_noun_phrases(text)
        article_phrases[article['url']] = phrases
        for phrase in phrases:
            phrase_counts[phrase] += 1

    # Find clusters: phrases appearing in min_cluster_size+ rejected articles
    existing_keywords = _load_existing_keywords()
    emerging = []

    for phrase, count in phrase_counts.most_common(50):
        if count >= min_cluster_size and phrase.lower() not in existing_keywords:
            articles = [
                url for url, ph in article_phrases.items() if phrase in ph
            ]
            emerging.append({
                'phrase': phrase,
                'count': count,
                'example_articles': articles[:5],
                'suggested_action': f'Add "{phrase.lower()}" to Cat A project keywords',
            })

    print(f"  [ARCHETYPE] Scanned {len(canadian_rejected)} Canadian rejected articles "
          f"(of {len(rejected)} total)")
    print(f"  [ARCHETYPE] Found {len(emerging)} emerging patterns "
          f"(threshold: {min_cluster_size}+ articles)")

    for e in emerging:
        print(f"    - \"{e['phrase']}\" ({e['count']} articles)")

    return emerging


def run_archetype_audit(conn=None, days=30):
    """Entry point for --audit-archetypes CLI flag.

    Args:
        conn: sqlite3.Connection (will create one if not provided)
        days: look back N days (default 30)

    Returns:
        list of emerging archetype dicts
    """
    if conn is None:
        from db import init_db
        conn = init_db()

    print(f"\n{'=' * 60}")
    print(f"  ARCHETYPE AUDIT — scanning last {days} days of rejected articles")
    print(f"{'=' * 60}\n")

    emerging = audit_rejected_articles(conn, days=days)

    if not emerging:
        print("\n  No emerging archetypes detected.")
        return []

    print(f"\n  {'=' * 60}")
    print(f"  EMERGING ARCHETYPES: {len(emerging)}")
    print(f"  {'=' * 60}")
    for i, e in enumerate(emerging, 1):
        print(f"\n  {i}. \"{e['phrase']}\" — {e['count']} rejected articles")
        print(f"     Suggestion: {e['suggested_action']}")
        print(f"     Example URLs:")
        for url in e['example_articles'][:3]:
            print(f"       - {url}")

    return emerging


if __name__ == '__main__':
    import sys
    days = 30
    if '--days' in sys.argv:
        idx = sys.argv.index('--days')
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])

    run_archetype_audit(days=days)
