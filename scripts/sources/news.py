"""
News Intelligence Module
Fetches news from NewsAPI.org and scores for strike-related content.

API: NewsAPI.org /v2/everything
Docs: https://newsapi.org/docs/endpoints/everything
"""

import os
import requests
from datetime import datetime, timedelta, timezone

NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
BASE_URL = 'https://newsapi.org/v2/everything'

# Keywords to search for
SEARCH_QUERIES = [
    'Iran attack military',
    'Israel strike Iran',
    'US Iran military',
    'Iran nuclear strike',
    'Pentagon Iran',
]

# Alert keywords that indicate high-risk content
ALERT_KEYWORDS = [
    'strike', 'attack', 'bomb', 'military action', 'war',
    'invasion', 'missile', 'airstrikes', 'troops deploy',
    'nuclear', 'retaliation', 'escalation', 'combat',
    'fighter jets', 'carrier', 'warship'
]


def fetch_news():
    """
    Fetch news articles from NewsAPI.
    Raises exception on failure - no fallback data.
    """
    if not NEWS_API_KEY:
        raise ValueError('NEWS_API_KEY environment variable not set')

    all_articles = []
    seen_titles = set()

    # Search from last 7 days (NewsAPI requires YYYY-MM-DD format)
    from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')

    for query in SEARCH_QUERIES:
        params = {
            'q': query,
            'from': from_date,
            'sortBy': 'publishedAt',
            'language': 'en',
            'pageSize': 20,
            'apiKey': NEWS_API_KEY
        }

        response = requests.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        if data.get('status') != 'ok':
            raise ValueError(f"NewsAPI error: {data.get('message', 'Unknown error')}")

        for article in data.get('articles', []):
            title = article.get('title', '')
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_articles.append(article)

    return all_articles


def score_article(article):
    """
    Check if an article contains alert keywords.
    Returns True if article is considered a critical alert.
    """
    title = (article.get('title') or '').lower()
    description = (article.get('description') or '').lower()
    content = title + ' ' + description

    for keyword in ALERT_KEYWORDS:
        if keyword.lower() in content:
            return True

    return False


def get_news_risk():
    """
    Fetch news and calculate risk score.
    Returns dict with risk, detail, and raw_data.
    """
    articles = fetch_news()

    # Score each article
    scored_articles = []
    critical_count = 0

    for article in articles:
        is_alert = score_article(article)
        if is_alert:
            critical_count += 1

        scored_articles.append({
            'title': article.get('title', 'Unknown'),
            'source': article.get('source', {}).get('name', 'Unknown'),
            'url': article.get('url', ''),
            'publishedAt': article.get('publishedAt', ''),
            'is_alert': is_alert
        })

    # Calculate risk score
    # Base: number of articles (more coverage = higher risk)
    # Boost: critical articles count significantly more
    article_count = len(scored_articles)

    if article_count == 0:
        risk = 0
    else:
        # Base risk from article count (0-30 range)
        base_risk = min(30, article_count * 1.5)

        # Critical article boost (0-70 range)
        critical_boost = min(70, critical_count * 7)

        risk = int(min(100, base_risk + critical_boost))

    return {
        'risk': risk,
        'detail': f'{article_count} articles, {critical_count} critical',
        'raw_data': {
            'articles': scored_articles[:25],  # Limit to 25 for JSON size
            'total_articles': article_count,
            'critical_count': critical_count,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    }


if __name__ == '__main__':
    # Test the module
    import json
    result = get_news_risk()
    print(json.dumps(result, indent=2))
