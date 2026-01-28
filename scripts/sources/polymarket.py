"""
Polymarket Module
Fetches prediction market odds for US/Israel strike on Iran.

API: Polymarket Gamma Markets API
Docs: https://docs.polymarket.com/developers/gamma-markets-api/get-events
Base URL: https://gamma-api.polymarket.com
No authentication required (public read-only access).

Query params for /events:
- slug: array of strings to filter by event slug
- closed: boolean to filter by closed status
"""

import json
import requests
from datetime import datetime

BASE_URL = 'https://gamma-api.polymarket.com'

# Target event slugs for Iran strike markets (avoiding near-term expiry)
TARGET_EVENTS = [
    {
        'slug': 'usisrael-strikes-iran-by',
        'name': 'US/Israel strikes Iran',
        'preferred_markets': ['February 28', 'March 31', 'June 30']
    },
    {
        'slug': 'israel-strikes-iran-by-june-30-2026',
        'name': 'Israel strikes Iran by June 30',
        'preferred_markets': ['June 30']
    },
    {
        'slug': 'us-x-iran-military-engagement-by',
        'name': 'US x Iran Military Engagement',
        'preferred_markets': ['March 31', 'June 30']
    },
]


def fetch_events_by_slugs(slugs):
    """
    Fetch events by their slugs from Gamma API.
    Uses the slug query parameter which accepts an array.

    Docs: https://docs.polymarket.com/developers/gamma-markets-api/get-events
    """
    url = f'{BASE_URL}/events'

    # Build params with multiple slug values
    params = [('slug', s) for s in slugs]
    params.append(('closed', 'false'))

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


def get_market_price(market):
    """
    Extract YES price from market's outcomePrices.
    outcomePrices is a JSON string: '["yes_price", "no_price"]'
    """
    prices_raw = market.get('outcomePrices')

    if not prices_raw:
        return None

    try:
        # Parse JSON string to list
        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw

        if prices and len(prices) >= 1:
            return float(prices[0])
    except (ValueError, TypeError, json.JSONDecodeError):
        pass

    return None


def find_best_market(event, preferred_dates):
    """
    Find the best market from an event based on preferred dates.
    Returns the market with highest preference that has valid prices.
    """
    markets = event.get('markets', [])

    if not markets:
        return None

    # Try preferred dates in order
    for date_str in preferred_dates:
        for market in markets:
            question = market.get('question', '')
            if date_str.lower() in question.lower():
                price = get_market_price(market)
                if price is not None and price > 0:
                    return market

    # Fallback: first market with valid price
    for market in markets:
        price = get_market_price(market)
        if price is not None and price > 0:
            return market

    return None


def get_polymarket_risk():
    """
    Get prediction market odds for Iran strike.
    Fetches target events by slug and returns averaged risk.
    """
    slugs = [t['slug'] for t in TARGET_EVENTS]
    events = fetch_events_by_slugs(slugs)

    # Map events by slug for lookup
    events_by_slug = {e.get('slug'): e for e in events}

    results = []

    for target in TARGET_EVENTS:
        event = events_by_slug.get(target['slug'])

        if not event:
            continue

        market = find_best_market(event, target['preferred_markets'])

        if not market:
            continue

        price = get_market_price(market)

        if price is None:
            continue

        results.append({
            'event_slug': target['slug'],
            'event_name': target['name'],
            'market_question': market.get('question', ''),
            'price': price,
            'odds_percent': int(price * 100)
        })

    if not results:
        raise ValueError('No valid Iran strike markets found on Polymarket')

    # Average odds across all markets
    avg_odds = sum(r['odds_percent'] for r in results) / len(results)
    risk = int(avg_odds)

    # Best market for detail display
    best = max(results, key=lambda r: r['odds_percent'])

    return {
        'risk': risk,
        'detail': f"{best['odds_percent']}% odds",
        'raw_data': {
            'odds': risk,
            'markets': results,
            'best_market': best['market_question'],
            'timestamp': datetime.utcnow().isoformat()
        }
    }


if __name__ == '__main__':
    import json
    result = get_polymarket_risk()
    print(json.dumps(result, indent=2))
