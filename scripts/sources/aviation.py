"""
Civil Aviation Module - Rolling Baseline
Monitors civilian air traffic over Iran using OpenSky Network API.

GROUNDED METHODOLOGY:
- Uses rolling 24-hour baseline from own historical data
- Risk = percentage deviation from rolling average
- Lower traffic than normal = higher risk (airspace avoidance)

Research basis:
- Normal Iran overflight: 1,000-1,400 daily (Source: News Central Asia)
- Key indicator: sudden drops in traffic, not absolute numbers
- NOTAM/FIR closures are strongest signal (future enhancement)

API: OpenSky Network REST API /states/all
Docs: https://openskynetwork.github.io/opensky-api/rest.html
Uses anonymous access (no authentication required).
"""

import requests
from datetime import datetime, timezone

BASE_URL = 'https://opensky-network.org/api/states/all'

# Iran bounding box (accurate)
# Source: https://gist.github.com/graydon/11198540
IRAN_BBOX = {
    'lamin': 25.08,   # Southern coast (Persian Gulf)
    'lamax': 39.71,   # Northern border (Azerbaijan/Armenia)
    'lomin': 44.11,   # Western border (Iraq/Turkey)
    'lomax': 63.32    # Eastern border (Afghanistan/Pakistan)
}

# Persian Gulf region (international waters + coastal areas)
PERSIAN_GULF_BBOX = {
    'lamin': 23.5,    # South of Qatar/UAE
    'lamax': 30.5,    # Kuwait/Iran coast
    'lomin': 47.5,    # Kuwait coast
    'lomax': 58.0     # Oman/Strait of Hormuz
}

# Minimum history needed for rolling baseline
MIN_HISTORY_FOR_BASELINE = 6  # ~1 hour at 10-min intervals


def fetch_aircraft(bbox):
    """
    Fetch aircraft states within a bounding box.
    Uses anonymous access (no authentication).
    """
    params = {
        'lamin': bbox['lamin'],
        'lamax': bbox['lamax'],
        'lomin': bbox['lomin'],
        'lomax': bbox['lomax']
    }

    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


def count_airborne(data):
    """
    Count airborne aircraft from OpenSky response.
    """
    states = data.get('states') or []
    count = 0

    for state in states:
        if len(state) >= 9:
            on_ground = state[8]
            if not on_ground:
                count += 1

    return count


def calculate_risk_from_baseline(current_count, history):
    """
    Calculate risk based on deviation from rolling baseline.

    Grounded methodology:
    - If insufficient history, use conservative estimate
    - Otherwise, calculate % deviation from rolling average
    - Lower traffic = higher risk (potential airspace avoidance)

    Risk tiers (based on research):
    - Normal (within 20% of baseline): 0-20 risk
    - Concern (20-40% drop): 20-50 risk
    - Alert (40-60% drop): 50-80 risk
    - Critical (>60% drop): 80-100 risk

    Returns: risk score 0-100
    """
    if len(history) < MIN_HISTORY_FOR_BASELINE:
        # Cold start: use conservative linear estimate
        # We expect ~50-100 aircraft in combined region per snapshot
        # Lower than 30 is concerning, 0 is critical
        if current_count >= 50:
            return 0
        elif current_count >= 30:
            return int((50 - current_count) * 2)  # 0-40
        elif current_count >= 10:
            return int(40 + (30 - current_count) * 2)  # 40-80
        else:
            return min(100, 80 + (10 - current_count) * 2)  # 80-100

    # Calculate rolling baseline
    baseline = sum(history) / len(history)

    if baseline <= 0:
        baseline = 1  # Avoid division by zero

    # Calculate deviation (negative = drop in traffic)
    deviation = (baseline - current_count) / baseline

    # Convert deviation to risk
    # Positive deviation = traffic drop = higher risk
    if deviation <= 0:
        # Traffic at or above baseline = low risk
        return max(0, int(-deviation * 20))  # 0-20 for increases
    elif deviation < 0.2:
        # Within 20% of baseline = normal
        return int(deviation * 100)  # 0-20
    elif deviation < 0.4:
        # 20-40% drop = concern
        return int(20 + (deviation - 0.2) * 150)  # 20-50
    elif deviation < 0.6:
        # 40-60% drop = alert
        return int(50 + (deviation - 0.4) * 150)  # 50-80
    else:
        # >60% drop = critical
        return min(100, int(80 + (deviation - 0.6) * 50))  # 80-100


def get_aviation_risk(history=None):
    """
    Monitor civilian aviation over Iran and calculate risk score.
    Uses rolling baseline from historical data.

    Args:
        history: List of previous total aircraft counts (for rolling baseline)

    Returns dict with risk, detail, and raw_data.
    """
    if history is None:
        history = []

    # Get aircraft counts
    iran_data = fetch_aircraft(IRAN_BBOX)
    iran_count = count_airborne(iran_data)

    gulf_data = fetch_aircraft(PERSIAN_GULF_BBOX)
    gulf_count = count_airborne(gulf_data)

    total_count = iran_count + gulf_count

    # Calculate risk from rolling baseline
    risk = calculate_risk_from_baseline(total_count, history)

    # Calculate baseline stats for transparency
    if len(history) >= MIN_HISTORY_FOR_BASELINE:
        baseline_avg = sum(history) / len(history)
        deviation_pct = ((baseline_avg - total_count) / baseline_avg * 100) if baseline_avg > 0 else 0
    else:
        baseline_avg = None
        deviation_pct = None

    return {
        'risk': risk,
        'detail': f'{total_count} flights in region',
        'raw_data': {
            'total_count': total_count,
            'iran_count': iran_count,
            'gulf_count': gulf_count,
            'baseline_avg': round(baseline_avg, 1) if baseline_avg else None,
            'deviation_pct': round(deviation_pct, 1) if deviation_pct is not None else None,
            'history_length': len(history),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    }


if __name__ == '__main__':
    import json
    # Test with no history (cold start)
    result = get_aviation_risk()
    print(json.dumps(result, indent=2))
