"""
Military Tanker Module - Rolling Baseline
Tracks aerial refueling aircraft in the Middle East region using OpenSky Network.

GROUNDED METHODOLOGY:
- Uses rolling 7-day baseline from own historical data
- Risk = deviation from rolling average
- "Surge" = >2x rolling average or >12 tankers simultaneously

Research basis:
- Normal: Small persistent presence at Al Udeid/Prince Sultan
- Surge indicator: "Over two dozen" is historically significant
- 2019: Surge preceded Iraq strikes
- 2025: Surge preceded Iran strikes
Source: https://www.armyrecognition.com/news/aerospace-news/2025/

API: OpenSky Network REST API /states/all
Docs: https://openskynetwork.github.io/opensky-api/rest.html
Uses anonymous access (no authentication required).

CONFIDENCE: MEDIUM - callsign matching is unreliable, many military aircraft don't broadcast
"""

import requests
from datetime import datetime, timezone

BASE_URL = 'https://opensky-network.org/api/states/all'

# Wider Middle East bounding box
# Covers: Eastern Mediterranean, Arabian Peninsula, Persian Gulf, Iraq, Iran
MIDDLE_EAST_BBOX = {
    'lamin': 12.0,    # South Yemen
    'lamax': 42.2,    # Northern Turkey
    'lomin': 32.0,    # Eastern Mediterranean
    'lomax': 63.5     # Eastern Iran
}

# Known military tanker callsign prefixes
TANKER_CALLSIGN_PREFIXES = [
    'KING',    # KC-135
    'SHELL',   # KC-135
    'TEXCO',   # KC-135 variant
    'PETRO',   # KC-135 variant
    'GUCCI',   # KC-10
    'ARCO',    # Tanker
    'ESSO',    # Tanker
    'MOBIL',   # Tanker
    'PACK',    # KC-46
    'ATOM',    # Tanker
    'TREK',    # Tanker
    'PEARL',   # UK tanker
    'ASCOT',   # RAF tanker
    'RRR',     # USAF refueling
    'QUID',    # Tanker
    'BRASS',   # Tanker
]

# Minimum history for baseline calculation
MIN_HISTORY_FOR_BASELINE = 6

# Surge threshold (absolute) - based on research: "dozens" = ~12+
SURGE_THRESHOLD = 12


def fetch_aircraft(bbox):
    """Fetch aircraft states within a bounding box."""
    params = {
        'lamin': bbox['lamin'],
        'lamax': bbox['lamax'],
        'lomin': bbox['lomin'],
        'lomax': bbox['lomax']
    }

    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


def is_tanker(callsign):
    """Check if an aircraft might be a military tanker based on callsign."""
    if not callsign:
        return False

    callsign_upper = callsign.upper().strip()

    for prefix in TANKER_CALLSIGN_PREFIXES:
        if callsign_upper.startswith(prefix):
            return True

    return False


def calculate_risk_from_baseline(tanker_count, history):
    """
    Calculate risk based on deviation from rolling baseline.

    Grounded methodology:
    - If insufficient history, use absolute thresholds
    - Otherwise, flag surge when >2x rolling average
    - Also flag if >12 tankers (absolute surge threshold from research)

    Risk tiers:
    - 0 tankers: 0 risk
    - Normal (at/below baseline): 10-30 risk
    - Elevated (1.5x baseline): 40-60 risk
    - Surge (2x baseline or >12): 70-100 risk
    """
    # Absolute surge check first
    if tanker_count >= SURGE_THRESHOLD:
        return min(100, 70 + (tanker_count - SURGE_THRESHOLD) * 3)

    if tanker_count == 0:
        return 0

    if len(history) < MIN_HISTORY_FOR_BASELINE:
        # Cold start: use simple scaling
        # 1-2 tankers = normal (20-30)
        # 3-5 tankers = elevated (40-60)
        # 6+ tankers = high (70+)
        if tanker_count <= 2:
            return 10 + tanker_count * 10
        elif tanker_count <= 5:
            return 30 + (tanker_count - 2) * 10
        else:
            return min(100, 60 + (tanker_count - 5) * 10)

    # Calculate rolling baseline
    baseline = sum(history) / len(history)

    if baseline <= 0:
        baseline = 0.5  # Assume small baseline if no historical tankers

    # Calculate ratio to baseline
    ratio = tanker_count / baseline

    if ratio <= 1.0:
        # At or below baseline
        return int(10 + ratio * 20)  # 10-30
    elif ratio <= 1.5:
        # Slightly elevated
        return int(30 + (ratio - 1.0) * 40)  # 30-50
    elif ratio <= 2.0:
        # Elevated
        return int(50 + (ratio - 1.5) * 40)  # 50-70
    else:
        # Surge (>2x baseline)
        return min(100, int(70 + (ratio - 2.0) * 15))  # 70-100


def get_tanker_risk(history=None):
    """
    Track military tankers in the Middle East and calculate risk score.
    Uses rolling baseline from historical data.

    Args:
        history: List of previous tanker counts (for rolling baseline)

    Returns dict with risk, detail, and raw_data.
    """
    if history is None:
        history = []

    # Fetch all aircraft in region
    data = fetch_aircraft(MIDDLE_EAST_BBOX)
    states = data.get('states') or []

    tankers = []

    for state in states:
        if len(state) >= 17:
            callsign = (state[1] or '').strip()
            origin_country = state[2]
            on_ground = state[8]

            if on_ground:
                continue

            if is_tanker(callsign):
                tankers.append({
                    'icao24': state[0],
                    'callsign': callsign,
                    'origin_country': origin_country,
                    'latitude': state[6],
                    'longitude': state[5],
                    'altitude': state[7] or state[13],
                    'velocity': state[9]
                })

    tanker_count = len(tankers)
    callsigns = [t['callsign'] for t in tankers]

    # Calculate risk from rolling baseline
    risk = calculate_risk_from_baseline(tanker_count, history)

    # Determine status
    if len(history) >= MIN_HISTORY_FOR_BASELINE:
        baseline_avg = sum(history) / len(history)
        ratio = tanker_count / baseline_avg if baseline_avg > 0 else 0
        is_surge = tanker_count >= SURGE_THRESHOLD or ratio >= 2.0
    else:
        baseline_avg = None
        ratio = None
        is_surge = tanker_count >= SURGE_THRESHOLD

    status = 'SURGE' if is_surge else ('elevated' if risk >= 50 else 'normal')

    return {
        'risk': risk,
        'detail': f'{tanker_count} detected ({status})',
        'raw_data': {
            'tanker_count': tanker_count,
            'callsigns': callsigns,
            'baseline_avg': round(baseline_avg, 1) if baseline_avg else None,
            'ratio_to_baseline': round(ratio, 2) if ratio else None,
            'is_surge': is_surge,
            'history_length': len(history),
            'tankers': tankers[:10],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    }


if __name__ == '__main__':
    import json
    result = get_tanker_risk()
    print(json.dumps(result, indent=2))
