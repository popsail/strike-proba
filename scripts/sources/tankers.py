"""
Military Tanker Module
Tracks aerial refueling aircraft in the Middle East region using OpenSky Network.

API: OpenSky Network REST API /states/all
Docs: https://openskynetwork.github.io/opensky-api/rest.html
"""

import os
import requests
from datetime import datetime

OPENSKY_CLIENT_ID = os.environ.get('OPENSKY_CLIENT_ID')
OPENSKY_CLIENT_SECRET = os.environ.get('OPENSKY_CLIENT_SECRET')

BASE_URL = 'https://opensky-network.org/api/states/all'
TOKEN_URL = 'https://opensky-network.org/api/auth/token'

# Wider Middle East bounding box
# Covers: Eastern Mediterranean, Arabian Peninsula, Persian Gulf, Iraq, Iran
MIDDLE_EAST_BBOX = {
    'lamin': 12.0,   # South of Yemen
    'lamax': 42.0,   # Turkey
    'lomin': 30.0,   # Eastern Mediterranean
    'lomax': 65.0    # Eastern Iran/Pakistan border
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

# Countries that operate significant tanker fleets in the region
TANKER_COUNTRIES = ['United States', 'United Kingdom', 'France', 'Israel']


def get_oauth_token():
    """
    Get OAuth2 access token from OpenSky Network.
    """
    if not OPENSKY_CLIENT_ID or not OPENSKY_CLIENT_SECRET:
        raise ValueError('OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET must be set')

    response = requests.post(
        TOKEN_URL,
        data={
            'grant_type': 'client_credentials',
            'client_id': OPENSKY_CLIENT_ID,
            'client_secret': OPENSKY_CLIENT_SECRET
        },
        timeout=30
    )
    response.raise_for_status()

    data = response.json()
    return data.get('access_token')


def fetch_aircraft(bbox, token):
    """
    Fetch aircraft states within a bounding box.
    """
    headers = {
        'Authorization': f'Bearer {token}'
    }

    params = {
        'lamin': bbox['lamin'],
        'lamax': bbox['lamax'],
        'lomin': bbox['lomin'],
        'lomax': bbox['lomax']
    }

    response = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    return response.json()


def is_tanker(callsign, origin_country):
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
    token = get_oauth_token()

    # Fetch all aircraft in region
    data = fetch_aircraft(MIDDLE_EAST_BBOX, token)
    states = data.get('states', [])

    tankers = []

    for state in states:
        if len(state) >= 17:
            callsign = (state[1] or '').strip()
            origin_country = state[2]
            on_ground = state[8]

            # Only consider airborne aircraft
            if on_ground:
                continue

            if is_tanker(callsign, origin_country):
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
