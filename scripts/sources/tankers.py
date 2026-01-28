"""
Military Tanker Module
Tracks aerial refueling aircraft in the Middle East region using OpenSky Network.

API: OpenSky Network REST API /states/all
Docs: https://openskynetwork.github.io/opensky-api/rest.html

Uses anonymous access (no authentication required).
"""

import requests
from datetime import datetime

BASE_URL = 'https://opensky-network.org/api/states/all'

# Wider Middle East bounding box
# Covers: Eastern Mediterranean, Arabian Peninsula, Persian Gulf, Iraq, Iran
# Based on country bounding boxes from https://gist.github.com/graydon/11198540
MIDDLE_EAST_BBOX = {
    'lamin': 12.0,    # South Yemen (12.1°N)
    'lamax': 42.2,    # Northern Turkey (42.1°N)
    'lomin': 32.0,    # Eastern Mediterranean/Israel (34.3°E with buffer)
    'lomax': 63.5     # Eastern Iran border (63.3°E)
}

# Known military tanker callsign prefixes
# US Air Force tankers: KC-135 (KING, SHELL), KC-10 (GUCCI), KC-46
# Also generic refueling callsigns
TANKER_CALLSIGN_PREFIXES = [
    'KING',    # KC-135 common callsign
    'SHELL',   # KC-135 common callsign
    'TEXCO',   # KC-135 variant
    'PETRO',   # KC-135 variant
    'GUCCI',   # KC-10 common callsign
    'ARCO',    # Tanker callsign
    'ESSO',    # Tanker callsign
    'MOBIL',   # Tanker callsign
    'PACK',    # KC-46
    'ATOM',    # Tanker callsign
    'TREK',    # Tanker callsign
    'PEARL',   # UK tanker
    'ASCOT',   # RAF tanker
    'RRR',     # USAF refueling
    'QUID',    # Tanker
    'BRASS',   # Tanker
]


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


def is_tanker(callsign):
    """
    Check if an aircraft might be a military tanker based on callsign.
    """
    if not callsign:
        return False

    callsign_upper = callsign.upper().strip()

    # Check callsign prefixes
    for prefix in TANKER_CALLSIGN_PREFIXES:
        if callsign_upper.startswith(prefix):
            return True

    return False


def get_tanker_risk():
    """
    Track military tankers in the Middle East and calculate risk score.
    More tankers = higher risk (refueling support for operations).
    """
    # Fetch all aircraft in region
    data = fetch_aircraft(MIDDLE_EAST_BBOX)
    states = data.get('states') or []

    tankers = []

    for state in states:
        if len(state) >= 17:
            callsign = (state[1] or '').strip()
            origin_country = state[2]
            on_ground = state[8]

            # Only consider airborne aircraft
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

    # Risk calculation:
    # 0 tankers = 0 risk
    # 1-2 tankers = 20-40 risk (normal operations)
    # 3-5 tankers = 50-70 risk (elevated activity)
    # 6+ tankers = 80-100 risk (surge activity)
    if tanker_count == 0:
        risk = 0
    elif tanker_count <= 2:
        risk = tanker_count * 20
    elif tanker_count <= 5:
        risk = 30 + (tanker_count - 2) * 15
    else:
        risk = min(100, 75 + (tanker_count - 5) * 5)

    return {
        'risk': risk,
        'detail': f'{tanker_count} detected in region',
        'raw_data': {
            'tanker_count': tanker_count,
            'callsigns': callsigns,
            'tankers': tankers[:10],  # Limit details
            'timestamp': datetime.utcnow().isoformat()
        }
    }


if __name__ == '__main__':
    import json
    result = get_tanker_risk()
    print(json.dumps(result, indent=2))
