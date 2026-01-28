"""
Polymarket Module
Fetches prediction market odds for US/Israel strike on Iran.

API: Polymarket Gamma Markets API
Docs: https://docs.polymarket.com/developers/gamma-markets-api/overview
Base URL: https://gamma-api.polymarket.com
No authentication required (public read-only access).
"""

import requests
from datetime import datetime

BASE_URL = 'https://gamma-api.polymarket.com'

# Search terms to find relevant markets
IRAN_SEARCH_TERMS = [
    'Iran strike',
    'Iran attack',
    'Israel Iran',
    'US Iran military',
    'bomb Iran',
]


def search_markets(query):
    """
    Search for markets matching query.
    """
    url = f'{BASE_URL}/markets'

    params = {
        'limit': 50,
        'active': 'true',
        'closed': 'false'
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    markets = response.json()

    # Filter markets by query (case-insensitive)
    query_lower = query.lower()
    matching = []

    for market in markets:
        question = (market.get('question') or '').lower()
        description = (market.get('description') or '').lower()

        if query_lower in question or query_lower in description:
            matching.append(market)

    return matching


def get_market_price(market):
    """
    Get current price (probability) for a market.
    Price is typically 0-1 representing probability.
    """
    # Polymarket markets have outcomes with prices
    # For binary markets, YES price = probability
    outcomes = market.get('outcomes', [])
    outcome_prices = market.get('outcomePrices', [])

    if outcome_prices and len(outcome_prices) > 0:
        # First outcome is typically "Yes"
        try:
            return float(outcome_prices[0])
        except (ValueError, TypeError):
            pass

    # Try alternative price field
    price = market.get('price')
    if price is not None:
        try:
            return float(price)
        except (ValueError, TypeError):
            pass

    return None


def find_iran_strike_market():
    """
    Find the most relevant Iran strike prediction market.
    """
    all_markets = []

    for term in IRAN_SEARCH_TERMS:
        try:
            markets = search_markets(term)
            all_markets.extend(markets)
        except Exception:
            continue

    # Deduplicate by market ID
    seen_ids = set()
    unique_markets = []
    for market in all_markets:
        market_id = market.get('id')
        if market_id and market_id not in seen_ids:
            seen_ids.add(market_id)
            unique_markets.append(market)

    # Score markets by relevance
    def relevance_score(market):
        question = (market.get('question') or '').lower()
        score = 0

        # Boost for key terms
        if 'iran' in question:
            score += 10
        if 'strike' in question or 'attack' in question:
            score += 10
        if 'israel' in question:
            score += 5
        if 'us' in question or 'united states' in question or 'america' in question:
            score += 5
        if 'military' in question:
            score += 3
        if 'bomb' in question:
            score += 3

        # Boost for active trading (volume)
        volume = market.get('volume', 0)
        if volume:
            try:
                score += min(20, int(float(volume) / 10000))
            except (ValueError, TypeError):
                pass

        return score

    # Sort by relevance
    unique_markets.sort(key=relevance_score, reverse=True)

    return unique_markets[0] if unique_markets else None


def get_polymarket_risk():
    """
    Get prediction market odds for Iran strike.
    """
    market = find_iran_strike_market()

    if not market:
        raise ValueError('No relevant Iran strike market found on Polymarket')

    price = get_market_price(market)

    if price is None:
        raise ValueError('Could not get price for market')

    # Convert price to percentage (0-100)
    odds_percent = int(price * 100)
    risk = odds_percent  # Direct mapping: market odds = risk

    question = market.get('question', 'Unknown market')

    return {
        'risk': risk,
        'detail': f'{odds_percent}% odds',
        'raw_data': {
            'odds': odds_percent,
            'price': price,
            'market': question,
            'market_id': market.get('id'),
            'volume': market.get('volume'),
            'timestamp': datetime.utcnow().isoformat()
        }
    }


if __name__ == '__main__':
    import json
    result = get_polymarket_risk()
    print(json.dumps(result, indent=2))
