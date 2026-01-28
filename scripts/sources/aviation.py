"""
Civil Aviation Module
Monitors civilian air traffic over Iran using OpenSky Network API.

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
# Covers: Kuwait, Bahrain, Qatar, UAE, Oman coast, Iran coast
PERSIAN_GULF_BBOX = {
    'lamin': 23.5,    # South of Qatar/UAE
    'lamax': 30.5,    # Kuwait/Iran coast
    'lomin': 47.5,    # Kuwait coast
    'lomax': 58.0     # Oman/Strait of Hormuz
}

# Baseline expected aircraft count (typical busy period)
BASELINE_AIRCRAFT_IRAN = 80
BASELINE_AIRCRAFT_GULF = 50


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


def parse_states(data):
    """
    Parse OpenSky states response into aircraft list.
    State vector indices:
    0: icao24, 1: callsign, 2: origin_country, 3: time_position,
    4: last_contact, 5: longitude, 6: latitude, 7: baro_altitude,
    8: on_ground, 9: velocity, 10: true_track, 11: vertical_rate,
    12: sensors, 13: geo_altitude, 14: squawk, 15: spi, 16: position_source
    """
    states = data.get('states') or []
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
    # Get aircraft over Iran
    iran_data = fetch_aircraft(IRAN_BBOX)
    iran_aircraft = parse_states(iran_data)
    iran_count = len([a for a in iran_aircraft if not a['on_ground']])

    # Get aircraft over Persian Gulf
    gulf_data = fetch_aircraft(PERSIAN_GULF_BBOX)
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
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    }


if __name__ == '__main__':
    import json
    result = get_aviation_risk()
    print(json.dumps(result, indent=2))
