"""Fetch a curated Unsplash image based on headline keywords.

Free tier: 50 requests/hour. Pipeline runs once/week = 1 request/run.
Requires UNSPLASH_ACCESS_KEY environment variable.
"""
import os
import re

UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY', '')


def extract_search_terms(headline: str) -> str:
    """Extract 2-3 meaningful keywords from headline for image search."""
    stop = {
        'canada', 'canadian', 'the', 'a', 'an', 'as', 'in', 'of', 'to',
        'for', 'and', 'or', 'but', 'is', 'are', 'was', 'were', 'has',
        'have', 'had', 'be', 'been', 'will', 'would', 'could', 'should',
        'its', 'their', 'this', 'that', 'with', 'from', 'more', 'most',
        'also', 'over', 'after', 'before', 'while', 'sheds', 'faces',
        'amid', 'hits', 'sees', 'shows', 'posts', 'report', 'data',
    }
    words = re.findall(r'\b[a-zA-Z]{3,}\b', headline.lower())
    keywords = [w for w in words if w not in stop][:3]
    return ' '.join(keywords) + ' Canada economy'


def fetch_unsplash_image(headline: str) -> str | None:
    """Search Unsplash for a relevant landscape image. Returns URL or None."""
    if not UNSPLASH_ACCESS_KEY:
        return None
    if not headline:
        return None

    from urllib.parse import quote
    query = extract_search_terms(headline)
    url = (
        f'https://api.unsplash.com/search/photos'
        f'?query={quote(query)}&per_page=1&orientation=landscape'
    )
    headers = {'Authorization': f'Client-ID {UNSPLASH_ACCESS_KEY}'}

    try:
        from urllib.request import Request, urlopen
        import json as _json
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                results = _json.loads(resp.read()).get('results', [])
                if results:
                    return results[0]['urls']['regular']
    except Exception as e:
        print(f"  [IMAGE] Unsplash fetch error: {e}")

    return None
