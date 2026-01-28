"""
Civil Aviation Module
Monitors civilian air traffic over Iran using OpenSky Network API.

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

# Iran bounding box (approximate)
# Latitude: 25°N to 40°N
# Longitude: 44°E to 63°E
IRAN_BBOX = {
    'lamin': 25.0,
    'lamax': 40.0,
    'lomin': 44.0,
    'lomax': 63.0
}

# Extended Persian Gulf region
PERSIAN_GULF_BBOX = {
    'lamin': 23.0,
    'lamax': 32.0,
    'lomin': 48.0,
    'lomax': 60.0
}

# Baseline expected aircraft count (typical busy period)
BASELINE_AIRCRAFT_IRAN = 80
BASELINE_AIRCRAFT_GULF = 50


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


def parse_states(data):
    """
    Parse OpenSky states response into aircraft list.
    State vector indices:
    0: icao24, 1: callsign, 2: origin_country, 3: time_position,
    4: last_contact, 5: longitude, 6: latitude, 7: baro_altitude,
    8: on_ground, 9: velocity, 10: true_track, 11: vertical_rate,
    12: sensors, 13: geo_altitude, 14: squawk, 15: spi, 16: position_source
    """
    states = data.get('states', [])
    aircraft = []

    for state in states:
        if len(state) >= 17:
            aircraft.append({
                'icao24': state[0],
                'callsign': (state[1] or '').strip(),
                'origin_country': state[2],
                'latitude': state[6],
                'longitude': state[5],
                'altitude': state[7] or state[13],
                'on_ground': state[8],
                'velocity': state[9]
            })

    return aircraft


def get_aviation_risk():
    """
    Monitor civilian aviation over Iran and calculate risk score.
    Lower than normal traffic = higher risk (airspace avoidance).
    """
    token = get_oauth_token()

    # Get aircraft over Iran
    iran_data = fetch_aircraft(IRAN_BBOX, token)
    iran_aircraft = parse_states(iran_data)
    iran_count = len([a for a in iran_aircraft if not a['on_ground']])

    # Get aircraft over Persian Gulf
    gulf_data = fetch_aircraft(PERSIAN_GULF_BBOX, token)
    gulf_aircraft = parse_states(gulf_data)
    gulf_count = len([a for a in gulf_aircraft if not a['on_ground']])

    # Calculate risk based on traffic deviation from baseline
    # Fewer aircraft than expected = potential airspace avoidance = higher risk
    iran_ratio = iran_count / BASELINE_AIRCRAFT_IRAN if BASELINE_AIRCRAFT_IRAN > 0 else 1
    gulf_ratio = gulf_count / BASELINE_AIRCRAFT_GULF if BASELINE_AIRCRAFT_GULF > 0 else 1

    # Invert: lower traffic = higher risk
    # Ratio 1.0 (normal) = 0 risk contribution
    # Ratio 0.5 (half traffic) = 50 risk
    # Ratio 0.0 (no traffic) = 100 risk
    iran_risk = max(0, min(100, int((1 - iran_ratio) * 100)))
    gulf_risk = max(0, min(100, int((1 - gulf_ratio) * 100)))

    # Combined risk (weighted average)
    combined_risk = int(iran_risk * 0.6 + gulf_risk * 0.4)

    total_aircraft = iran_count + gulf_count

    return {
        'risk': combined_risk,
        'detail': f'{total_aircraft} flights in region',
        'raw_data': {
            'iran_aircraft_count': iran_count,
            'gulf_aircraft_count': gulf_count,
            'iran_baseline': BASELINE_AIRCRAFT_IRAN,
            'gulf_baseline': BASELINE_AIRCRAFT_GULF,
            'iran_ratio': round(iran_ratio, 2),
            'gulf_ratio': round(gulf_ratio, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
    }


if __name__ == '__main__':
    import json
    result = get_aviation_risk()
    print(json.dumps(result, indent=2))
