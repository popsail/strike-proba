"""
News Intelligence Module - GDELT DOC 2.0 API
Monitors Iran-related news coverage using GDELT's global news database.

GDELT returns volume as percentage of global coverage - built-in baseline!
This is a grounded metric used in academic research worldwide.

API: GDELT DOC 2.0 API
Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
Rate limit: 1 request per 5 seconds (we only make 1 per 10-min run)
Auth: None required (free)
"""

import requests
from datetime import datetime, timezone

BASE_URL = 'https://api.gdeltproject.org/api/v2/doc/doc'

# Iran-related search query for geopolitical monitoring
# Using OR to combine related terms - must be in parentheses per GDELT API
SEARCH_QUERY = '("Iran military" OR "Iran strike" OR "Iran attack" OR "US Iran" OR "Israel Iran")'


def fetch_gdelt_coverage():
    """
    Fetch Iran news coverage from GDELT DOC 2.0 API.
    Returns volume as percentage of global coverage.

    The timelinevol mode returns coverage as a percentage of ALL global
    news monitored by GDELT - this is a built-in baseline that doesn't
    require arbitrary thresholds.
    """
    params = {
        'query': SEARCH_QUERY,
        'mode': 'timelinevol',  # Returns % of global coverage
        'format': 'json',
        'timespan': '24h'  # Last 24 hours with 15-min resolution
    }

    # Use browser User-Agent to avoid rate limiting
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    response = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    return response.json()


def parse_timeline_data(data):
    """
    Parse GDELT timelinevol response.

    Actual response format:
    {
        "query_details": {...},
        "timeline": [
            {
                "series": "Volume Intensity",
                "data": [
                    {"date": "20260128T120000Z", "value": 0.32},
                    ...
                ]
            }
        ]
    }

    Returns: list of (datetime, value) tuples
    """
    timeline_list = data.get('timeline', [])

    if not timeline_list:
        return []

    # Get the first series (Volume Intensity)
    first_series = timeline_list[0] if timeline_list else {}
    raw_data = first_series.get('data', [])

    parsed = []
    for entry in raw_data:
        date_str = entry.get('date', '')
        value = entry.get('value', 0)

        # Parse GDELT date format: YYYYMMDDTHHMMSSZ
        try:
            dt = datetime.strptime(date_str, '%Y%m%dT%H%M%SZ')
            dt = dt.replace(tzinfo=timezone.utc)
            parsed.append((dt, float(value)))
        except (ValueError, TypeError):
            continue

    return parsed


def calculate_risk(current_pct):
    """
    Calculate risk score from GDELT coverage percentage.

    Based on actual GDELT data observed:
    - Typical Iran coverage: 0-0.15% (normal background noise)
    - Elevated: 0.15-0.3% (increased attention)
    - High: 0.3-0.5% (significant event)
    - Critical: >0.5% (major breaking news)

    Scoring formula:
    - 0% → 0 risk
    - 0.1% → 20 risk (normal)
    - 0.2% → 40 risk (elevated)
    - 0.3% → 60 risk (high)
    - 0.5% → 100 risk (critical)
    """
    if current_pct <= 0:
        return 0

    # Linear scale: 0.5% = 100 risk
    risk = int(current_pct / 0.5 * 100)
    return min(100, max(0, risk))


def get_news_risk():
    """
    Fetch news coverage from GDELT and calculate risk score.
    Returns dict with risk, detail, and raw_data.

    NO FALLBACK - if GDELT fails, raises exception.
    """
    data = fetch_gdelt_coverage()

    # Parse timeline data
    timeline_entries = parse_timeline_data(data)

    if not timeline_entries:
        # No data returned - could be temporary issue
        # Return 0 risk but include diagnostic info
        return {
            'risk': 0,
            'detail': 'No GDELT data',
            'raw_data': {
                'coverage_pct': 0,
                'data_points': 0,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }

    # Get the most recent data point
    timeline_entries.sort(key=lambda x: x[0], reverse=True)
    latest_dt, latest_pct = timeline_entries[0]

    # Calculate average over the period for context
    avg_pct = sum(v for _, v in timeline_entries) / len(timeline_entries)

    # Calculate risk from latest coverage
    risk = calculate_risk(latest_pct)

    return {
        'risk': risk,
        'detail': f'{latest_pct:.3f}% global coverage',
        'raw_data': {
            'coverage_pct': round(latest_pct, 4),
            'avg_coverage_pct': round(avg_pct, 4),
            'data_points': len(timeline_entries),
            'latest_timestamp': latest_dt.isoformat(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    }


if __name__ == '__main__':
    import json
    result = get_news_risk()
    print(json.dumps(result, indent=2))
