"""
sentiment.py — Consumer sentiment collection for CAN-MACRO dashboard.

Blends three free Canadian consumer sentiment sources into a weekly
word cloud and topic summary:
  1. Reddit (public JSON, no API key)
  2. Google Trends Canada (pytrends)
  3. Canadian news comment sections (CBC Coral, if accessible)

Sentiment extraction via Gemini 2.5 Flash.

Usage:
    from sentiment import collect_sentiment
    result = collect_sentiment(articles=gdelt_articles)
    # result is a dict ready for Firestore consumer_sentiment field

    # Or test mode:
    python sentiment.py --test
"""

import json
import os
import re
import time
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────

SENTIMENT_ENABLED    = os.environ.get('SENTIMENT_ENABLED', 'true').lower() == 'true'
REDDIT_USER_AGENT    = os.environ.get('REDDIT_USER_AGENT', 'CanMacroDashboard/1.0')
REDDIT_DELAY         = float(os.environ.get('SENTIMENT_REDDIT_DELAY', '1.0'))
TRENDS_DELAY         = float(os.environ.get('SENTIMENT_TRENDS_DELAY', '2.0'))
MAX_TOPICS           = int(os.environ.get('SENTIMENT_MAX_TOPICS', '40'))
GEMINI_MODEL         = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

_HEADERS = {'User-Agent': f'{REDDIT_USER_AGENT} (by /u/CanMacroDashboard)'}

# ── Reddit Config ────────────────────────────────────────────────────────────

REDDIT_SUBS = [
    {
        "sub": "PersonalFinanceCanada",
        "weight": 1.0,
        "limit": 100,
    },
    {
        "sub": "canadahousing",
        "weight": 0.8,
        "limit": 75,
    },
    {
        "sub": "CanadianInvestor",
        "weight": 0.7,
        "limit": 75,
    },
    {
        "sub": "canada",
        "weight": 0.4,
        "limit": 50,
        "filter_keywords": [
            "economy", "inflation", "housing", "mortgage", "rate", "job",
            "employment", "wage", "grocery", "affordability", "tax", "tariff",
            "trade", "recession", "GDP", "bank", "cost of living", "rent",
            "immigration", "budget", "debt", "dollar", "oil", "gas price",
        ],
    },
]

# ── Sentiment Categories ─────────────────────────────────────────────────────

SENTIMENT_CATEGORIES = {
    "housing": ["mortgage", "rent", "housing", "condo", "home price", "real estate",
                 "home", "landlord", "tenant", "property", "down payment"],
    "cost_of_living": ["grocery", "food price", "inflation", "cost of living",
                        "affordability", "price", "expensive", "cost", "bill"],
    "employment": ["job", "layoff", "hiring", "unemployment", "wage", "salary",
                    "remote work", "work from home", "career", "fired"],
    "rates_banking": ["rate", "interest", "bank", "BoC", "savings", "GIC",
                       "prime rate", "variable", "fixed", "HISA"],
    "trade_tariffs": ["tariff", "trade", "export", "import", "US", "border",
                       "CUSMA", "softwood", "duty", "Trump"],
    "investment": ["stock", "TSX", "portfolio", "TFSA", "RRSP", "invest",
                    "ETF", "dividend", "crypto", "FHSA"],
}


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 1: REDDIT
# ══════════════════════════════════════════════════════════════════════════════

def fetch_reddit(max_retries: int = 2) -> dict:
    """
    Fetch top posts + comments from Canadian finance subreddits.
    Returns {corpus: str, post_count: int, comment_count: int}.
    """
    all_text = []
    total_posts = 0
    total_comments = 0

    for cfg in REDDIT_SUBS:
        sub = cfg['sub']
        limit = cfg['limit']
        weight = cfg['weight']
        filter_kw = cfg.get('filter_keywords')

        try:
            url = f'https://www.reddit.com/r/{sub}/top.json?t=week&limit={limit}'
            resp = requests.get(url, headers=_HEADERS, timeout=15)

            if resp.status_code == 429:
                print(f"  [Sentiment] Reddit rate-limited on r/{sub}, waiting 30s...")
                time.sleep(30)
                resp = requests.get(url, headers=_HEADERS, timeout=15)

            if resp.status_code != 200:
                print(f"  [Sentiment] Reddit r/{sub}: HTTP {resp.status_code}")
                continue

            data = resp.json()
            posts = data.get('data', {}).get('children', [])

            for post in posts:
                pd = post.get('data', {})
                title = pd.get('title', '')
                body = pd.get('selftext', '')
                score = pd.get('score', 0)
                post_id = pd.get('id', '')

                # Filter r/canada to economic topics
                if filter_kw:
                    combined = (title + ' ' + body).lower()
                    if not any(kw.lower() in combined for kw in filter_kw):
                        continue

                # Weight by score (upvotes indicate broader sentiment)
                weight_label = f"[score:{score}]" if score > 50 else ""
                all_text.append(f"[r/{sub}] {weight_label} {title}\n{body[:500]}")
                total_posts += 1

                # Fetch top 3 comments
                if post_id:
                    try:
                        time.sleep(REDDIT_DELAY)
                        cmt_url = f'https://www.reddit.com/r/{sub}/comments/{post_id}.json?limit=3&sort=top'
                        cmt_resp = requests.get(cmt_url, headers=_HEADERS, timeout=10)
                        if cmt_resp.status_code == 200:
                            cmt_data = cmt_resp.json()
                            if len(cmt_data) > 1:
                                comments = cmt_data[1].get('data', {}).get('children', [])
                                for cmt in comments[:3]:
                                    cmt_body = cmt.get('data', {}).get('body', '')
                                    cmt_score = cmt.get('data', {}).get('score', 0)
                                    if cmt_body and len(cmt_body) > 20:
                                        all_text.append(f"[comment r/{sub} score:{cmt_score}] {cmt_body[:300]}")
                                        total_comments += 1
                    except Exception:
                        pass

            time.sleep(REDDIT_DELAY)
            print(f"  [Sentiment] r/{sub}: {len(posts)} posts fetched")

        except Exception as e:
            print(f"  [Sentiment] Reddit r/{sub} error: {type(e).__name__}: {e}")

    return {
        'corpus': '\n\n'.join(all_text),
        'post_count': total_posts,
        'comment_count': total_comments,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 2: GOOGLE TRENDS CANADA
# ══════════════════════════════════════════════════════════════════════════════

def fetch_trends() -> dict:
    """
    Fetch rising/top queries from Google Trends for Canadian economic categories.
    Returns {data: str, query_count: int}.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("  [Sentiment] pytrends not installed — skipping Google Trends")
        return {'data': '', 'query_count': 0}

    # Category IDs: 7=Finance, 12=Business, 1163=Jobs, 179=Investing
    CATEGORIES = [7, 12, 1163, 179]
    CAT_NAMES = {7: 'Finance', 12: 'Business', 1163: 'Jobs', 179: 'Investing'}

    all_queries = []
    query_count = 0

    try:
        pytrends = TrendReq(hl='en-CA', tz=300)

        for cat in CATEGORIES:
            try:
                time.sleep(TRENDS_DELAY)
                pytrends.build_payload(kw_list=[''], cat=cat, geo='CA', timeframe='now 7-d')

                related = pytrends.related_queries()
                for kw, tables in related.items():
                    if tables is None:
                        continue
                    # Rising queries
                    rising = tables.get('rising')
                    if rising is not None and not rising.empty:
                        for _, row in rising.head(10).iterrows():
                            q = row.get('query', '')
                            val = row.get('value', 0)
                            all_queries.append(f"[Trends-{CAT_NAMES.get(cat,'')}-rising] {q} (value:{val})")
                            query_count += 1

                    # Top queries
                    top = tables.get('top')
                    if top is not None and not top.empty:
                        for _, row in top.head(5).iterrows():
                            q = row.get('query', '')
                            val = row.get('value', 0)
                            all_queries.append(f"[Trends-{CAT_NAMES.get(cat,'')}-top] {q} (value:{val})")
                            query_count += 1

                print(f"  [Sentiment] Google Trends cat {CAT_NAMES.get(cat,'')}: queries fetched")

            except Exception as e:
                print(f"  [Sentiment] Google Trends cat {cat} error: {type(e).__name__}")

    except Exception as e:
        print(f"  [Sentiment] Google Trends init error: {type(e).__name__}: {e}")

    return {
        'data': '\n'.join(all_queries),
        'query_count': query_count,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 3: NEWS COMMENTS (CBC Coral)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_news_comments(articles: list[dict] | None = None) -> dict:
    """
    Attempt to fetch comment threads from CBC articles already in the pipeline.
    Does NOT spend Tavily credits. Degrades gracefully.
    Returns {corpus: str, comment_count: int}.
    """
    if not articles:
        return {'corpus': '', 'comment_count': 0}

    # Filter to CBC articles only
    cbc_articles = [a for a in articles if 'cbc.ca' in (a.get('url', '') or '')]
    if not cbc_articles:
        return {'corpus': '', 'comment_count': 0}

    all_comments = []
    total = 0

    for art in cbc_articles[:10]:
        url = art.get('url', '')
        try:
            # CBC uses Coral/Talk comment system
            # Try the Coral API endpoint — this may not work if blocked
            # Extract story ID from URL path
            path_parts = url.rstrip('/').split('/')
            story_slug = path_parts[-1] if path_parts else ''

            # Coral GraphQL endpoint
            coral_url = 'https://talk.cbc.ca/api/v1/graph/ql'
            payload = {
                'query': '''
                    query($url: String!) {
                        story(url: $url) {
                            comments(first: 5, orderBy: REACTION_DESC) {
                                nodes { body }
                            }
                        }
                    }
                ''',
                'variables': {'url': url},
            }
            resp = requests.post(
                coral_url,
                json=payload,
                headers={'Content-Type': 'application/json', 'User-Agent': REDDIT_USER_AGENT},
                timeout=10,
            )

            if resp.status_code == 200:
                data = resp.json()
                nodes = (data.get('data', {}).get('story', {}) or {}).get('comments', {}).get('nodes', [])
                for node in nodes:
                    body = node.get('body', '')
                    if body and len(body) > 15:
                        all_comments.append(f"[CBC comment] {body[:300]}")
                        total += 1

            time.sleep(0.5)

        except Exception:
            # Graceful degradation — comments are supplementary
            pass

    if total:
        print(f"  [Sentiment] CBC comments: {total} collected from {len(cbc_articles)} articles")
    else:
        print("  [Sentiment] CBC comments: not accessible (using Reddit + Trends)")

    return {
        'corpus': '\n'.join(all_comments),
        'comment_count': total,
    }


# ══════════════════════════════════════════════════════════════════════════════
# GEMINI FLASH EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

SENTIMENT_PROMPT = """
You are analyzing Canadian consumer economic sentiment from this week's online discussions and search trends.

RAW TEXT FROM REDDIT (weighted by community relevance and upvotes):
{reddit_corpus}

GOOGLE TRENDS RISING QUERIES IN CANADA (Finance/Business/Jobs/Investing categories):
{trends_data}

NEWS COMMENT EXCERPTS (from CBC/Globe economic articles):
{comments_corpus}

Extract the top {max_topics} economic topics/phrases that Canadians are discussing or searching for this week. For each topic:

1. topic: short phrase (1-4 words) — e.g. "mortgage renewal", "grocery prices", "rate cut", "tariff fears", "job market", "housing bubble"
2. frequency: integer 1-100 representing relative prominence (100 = most discussed)
3. sentiment: one of "positive", "negative", "neutral", "mixed"
4. sentiment_score: float -1.0 (very negative) to +1.0 (very positive), 0.0 = neutral
5. source_blend: which sources contributed — "reddit", "trends", "comments", or combinations like "reddit+trends"
6. sample_context: one representative sentence or phrase from the source material that illustrates the sentiment (max 30 words)

Rules:
- Focus on ECONOMIC topics only: cost of living, housing, rates, employment, trade, investment, taxes, commodities, immigration (economic impact), government spending
- Exclude pure politics, sports, entertainment unless they have direct economic implications
- Merge similar topics: "mortgage rates" and "mortgage renewal" can be separate if sentiment differs, but "rate cut" and "interest rate cut" should merge
- Weight Reddit by upvotes (high-score posts = more representative)
- Weight Google Trends by "rising" status (breakout terms get higher frequency)
- If a topic appears in multiple sources, boost its frequency score
- Return valid JSON array, no markdown, no preamble

Return ONLY the JSON array.
"""


def extract_sentiment_gemini(
    reddit_corpus: str,
    trends_data: str,
    comments_corpus: str,
) -> list[dict]:
    """
    Send combined corpus to Gemini 2.5 Flash for structured sentiment extraction.
    Returns list of topic dicts.
    """
    try:
        from google import genai
        from google.genai import types

        api_key = os.environ.get('GEMINI_API_KEY', '') or os.environ.get('GOOGLE_API_KEY', '')
        api_key = api_key.strip()
        if not api_key:
            print("  [Sentiment] No Gemini API key — skipping extraction")
            return []

        client = genai.Client(api_key=api_key)

        # Truncate corpora to fit context
        prompt = SENTIMENT_PROMPT.format(
            reddit_corpus=reddit_corpus[:12000],
            trends_data=trends_data[:3000],
            comments_corpus=comments_corpus[:3000],
            max_topics=MAX_TOPICS,
        )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                max_output_tokens=4096,
            ),
        )

        raw = response.text.strip()
        topics = json.loads(raw)
        if isinstance(topics, list):
            print(f"  [Sentiment] Gemini extracted {len(topics)} topics")
            return topics
        return []

    except json.JSONDecodeError:
        print("  [Sentiment] Gemini returned invalid JSON — retrying with simpler prompt")
        try:
            # Retry with simpler prompt
            simple_prompt = (
                f"Extract top 20 economic discussion topics from this Canadian text. "
                f"Return JSON array with fields: topic (1-4 words), frequency (1-100), "
                f"sentiment_score (-1.0 to 1.0), sentiment (positive/negative/neutral/mixed), "
                f"source_blend, sample_context.\n\n"
                f"TEXT:\n{reddit_corpus[:6000]}\n\n{trends_data[:2000]}"
            )
            response2 = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=simple_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    max_output_tokens=2048,
                ),
            )
            topics2 = json.loads(response2.text.strip())
            return topics2 if isinstance(topics2, list) else []
        except Exception:
            print("  [Sentiment] Gemini retry also failed")
            return []

    except Exception as e:
        print(f"  [Sentiment] Gemini extraction error: {type(e).__name__}: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# AGGREGATE SENTIMENT
# ══════════════════════════════════════════════════════════════════════════════

def compute_sentiment_index(topics: list[dict]) -> dict:
    """
    Compute overall sentiment index and category breakdowns from extracted topics.
    Returns the full consumer_sentiment dict for Firestore.
    """
    if not topics:
        return None

    # Overall weighted average
    total_weight = sum(t.get('frequency', 1) for t in topics)
    if total_weight == 0:
        total_weight = 1
    weighted_sum = sum(
        t.get('sentiment_score', 0) * t.get('frequency', 1) for t in topics
    )
    overall_index = weighted_sum / total_weight

    # Category breakdowns
    category_scores = {}
    for cat_name, keywords in SENTIMENT_CATEGORIES.items():
        cat_topics = []
        for t in topics:
            topic_lower = (t.get('topic', '') or '').lower()
            if any(kw.lower() in topic_lower for kw in keywords):
                cat_topics.append(t)

        if cat_topics:
            cat_weight = sum(ct.get('frequency', 1) for ct in cat_topics)
            cat_sum = sum(ct.get('sentiment_score', 0) * ct.get('frequency', 1) for ct in cat_topics)
            cat_score = cat_sum / max(cat_weight, 1)
            top_topic = max(cat_topics, key=lambda x: x.get('frequency', 0))
            category_scores[cat_name] = {
                'score': round(cat_score, 3),
                'label': _sentiment_label(cat_score),
                'top_topic': top_topic.get('topic', ''),
                'topic_count': len(cat_topics),
            }
        else:
            category_scores[cat_name] = {
                'score': 0.0,
                'label': 'No Data',
                'top_topic': '',
                'topic_count': 0,
            }

    # Build categories list for frontend bar chart
    categories_list = []
    for cat_name in ['housing', 'cost_of_living', 'employment', 'rates_banking', 'trade_tariffs', 'investment']:
        cs = category_scores.get(cat_name, {})
        display_names = {
            'housing': 'Housing',
            'cost_of_living': 'Cost of Living',
            'employment': 'Employment',
            'rates_banking': 'Rates & Banking',
            'trade_tariffs': 'Trade & Tariffs',
            'investment': 'Investment',
        }
        categories_list.append({
            'name': display_names.get(cat_name, cat_name),
            'category': cat_name,
            'score': cs.get('score', 0),
            'label': cs.get('label', 'No Data'),
        })

    return {
        'overall_index': round(overall_index, 3),
        'overall_label': _sentiment_label(overall_index),
        'category_scores': category_scores,
        'categories': categories_list,
        'topics': topics,
        'collected_at': datetime.utcnow().isoformat() + 'Z',
    }


def _sentiment_label(score: float) -> str:
    """Convert numeric sentiment score to human-readable label."""
    if score > 0.25:
        return 'Optimistic'
    if score > 0.05:
        return 'Cautiously Positive'
    if score > -0.05:
        return 'Neutral'
    if score > -0.25:
        return 'Cautiously Negative'
    return 'Pessimistic'


# ══════════════════════════════════════════════════════════════════════════════
# MAIN COLLECTION FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def collect_sentiment(
    articles: list[dict] | None = None,
    test_mode: bool = False,
) -> dict | None:
    """
    Run the full sentiment collection pipeline.

    Parameters
    ----------
    articles : list[dict] | None
        GDELT/RSS articles already in the pipeline (for news comment extraction).
    test_mode : bool
        If True, print results to console instead of returning for Firestore.

    Returns
    -------
    dict | None
        The consumer_sentiment dict for Firestore, or None if all sources failed.
    """
    if not SENTIMENT_ENABLED:
        print("  [Sentiment] Disabled via SENTIMENT_ENABLED=false")
        return None

    print("\n  [Sentiment] Collecting consumer sentiment...")

    sources_summary = {
        'reddit_posts': 0,
        'reddit_comments': 0,
        'trends_queries': 0,
        'news_comments': 0,
    }
    failures = []

    # ── Source 1: Reddit ──
    try:
        reddit = fetch_reddit()
        sources_summary['reddit_posts'] = reddit['post_count']
        sources_summary['reddit_comments'] = reddit['comment_count']
    except Exception as e:
        print(f"  [Sentiment] Reddit collection failed: {type(e).__name__}")
        reddit = {'corpus': '', 'post_count': 0, 'comment_count': 0}
        failures.append('reddit')

    # ── Source 2: Google Trends ──
    try:
        trends = fetch_trends()
        sources_summary['trends_queries'] = trends['query_count']
    except Exception as e:
        print(f"  [Sentiment] Google Trends collection failed: {type(e).__name__}")
        trends = {'data': '', 'query_count': 0}
        failures.append('trends')

    # ── Source 3: News Comments ──
    try:
        comments = fetch_news_comments(articles)
        sources_summary['news_comments'] = comments['comment_count']
    except Exception as e:
        print(f"  [Sentiment] News comments failed: {type(e).__name__}")
        comments = {'corpus': '', 'comment_count': 0}
        failures.append('comments')

    # ── Check if we have ANY data ──
    total_text = len(reddit['corpus']) + len(trends['data']) + len(comments['corpus'])
    if total_text < 100:
        print("  [Sentiment] All sources failed or returned no data — skipping")
        return None

    # ── Gemini Flash Extraction ──
    topics = extract_sentiment_gemini(
        reddit_corpus=reddit['corpus'],
        trends_data=trends['data'],
        comments_corpus=comments['corpus'],
    )

    if not topics:
        print("  [Sentiment] Gemini extraction returned no topics — skipping")
        return None

    # ── Compute Aggregates ──
    result = compute_sentiment_index(topics)
    if result:
        result['sources_summary'] = sources_summary
        if failures:
            result['source_failures'] = failures

    # ── Test Mode Output ──
    if test_mode and result:
        print(f"\n  === SENTIMENT TEST RESULTS ===")
        print(f"  Overall: {result['overall_label']} ({result['overall_index']:+.3f})")
        print(f"  Sources: {sources_summary}")
        if failures:
            print(f"  Failures: {failures}")
        print(f"  Categories:")
        for cat, data in result.get('category_scores', {}).items():
            print(f"    {cat}: {data['score']:+.3f} ({data['label']}) — top: {data['top_topic']}")
        print(f"  Top 10 Topics:")
        for t in sorted(topics, key=lambda x: x.get('frequency', 0), reverse=True)[:10]:
            s = t.get('sentiment_score', 0)
            print(f"    {t.get('topic',''):25s} freq={t.get('frequency',0):3d}  sent={s:+.2f}  src={t.get('source_blend','')}")
        print(f"  =============================\n")

    if result:
        print(f"  [Sentiment] Complete: {result['overall_label']} ({result['overall_index']:+.3f}), "
              f"{len(topics)} topics, {sources_summary['reddit_posts']} Reddit posts")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Consumer sentiment collection')
    parser.add_argument('--test', action='store_true', help='Test mode — fetch and extract, print results')
    args = parser.parse_args()

    result = collect_sentiment(test_mode=True)
    if result:
        # Save to file for inspection
        out_path = f'sentiment_{datetime.now().strftime("%Y-%m-%d")}.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  Saved to {out_path}")
    else:
        print("  No sentiment data collected.")
