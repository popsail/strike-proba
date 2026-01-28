"""
Pentagon Pizza Meter Module
Monitors activity at pizza restaurants near the Pentagon using Outscraper API.

The "Pentagon Pizza Index" is a humorous but historically noted indicator:
unusual late-night pizza deliveries to the Pentagon have preceded military operations.

API: Outscraper Google Maps Places API
Docs: https://app.outscraper.com/api-docs
"""

import os
import requests
from datetime import datetime

OUTSCRAPER_API_KEY = os.environ.get('OUTSCRAPER_API_KEY')
BASE_URL = 'https://api.app.outscraper.com/maps/search-v3'

# Pizza places near Pentagon to monitor
# These are well-known pizza chains near the Pentagon
PENTAGON_PIZZA_PLACES = [
    "Domino's Pizza, Pentagon City, Arlington, VA",
    "Papa John's, Pentagon City, Arlington, VA",
    "Pizza Hut, Crystal City, Arlington, VA",
]

# Day indices (Monday = 0)
DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def fetch_place_data(query):
    """
    Fetch place data including popular times from Outscraper.
    """
    if not OUTSCRAPER_API_KEY:
        raise ValueError('OUTSCRAPER_API_KEY environment variable not set')

    headers = {
        'X-API-KEY': OUTSCRAPER_API_KEY
    }

    params = {
        'query': query,
        'limit': 1,
        'async': 'false'
    }

    response = requests.get(BASE_URL, params=params, headers=headers, timeout=60)
    response.raise_for_status()

    data = response.json()

    # Outscraper returns a list of results
    if data and len(data) > 0 and len(data[0]) > 0:
        return data[0][0]

    return None


def get_current_busyness(popular_times, now=None):
    """
    Get current busyness from popular_times data.
    popular_times format: list of 7 days, each with 'data' array of 24 hourly values.
    """
    if now is None:
        now = datetime.now()

    # Get current day (0=Monday in Python, but Google uses 0=Sunday sometimes)
    # Outscraper typically uses Monday=0
    day_index = now.weekday()
    hour = now.hour

    if not popular_times or len(popular_times) <= day_index:
        return None

    day_data = popular_times[day_index]

    if not day_data or 'data' not in day_data:
        return None

    hourly_data = day_data['data']

    if not hourly_data or len(hourly_data) <= hour:
        return None

    return hourly_data[hour]


def get_baseline_busyness(popular_times, day_index, hour):
    """
    Get average busyness for this hour across all days (baseline).
    """
    if not popular_times:
        return 50  # Default baseline

    total = 0
    count = 0

    for day in popular_times:
        if day and 'data' in day and len(day['data']) > hour:
            val = day['data'][hour]
            if val is not None and val > 0:
                total += val
                count += 1

    return total / count if count > 0 else 50


def get_pentagon_pizza_risk():
    """
    Monitor pizza place activity near Pentagon and calculate risk score.
    Higher than normal activity = elevated risk.
    """
    now = datetime.now()
    day_index = now.weekday()
    hour = now.hour

    # Check if it's late night (when unusual activity is more significant)
    is_late_night = hour >= 22 or hour < 6
    is_weekend = day_index >= 5

    places_data = []
    total_score = 0
    valid_places = 0

    for query in PENTAGON_PIZZA_PLACES:
        place = fetch_place_data(query)

        if not place:
            continue

        name = place.get('name', 'Unknown')
        popular_times = place.get('popular_times')

        current_busyness = None
        baseline = 50
        status = 'unknown'
        score = 50

        if popular_times:
            current_busyness = get_current_busyness(popular_times, now)
            baseline = get_baseline_busyness(popular_times, day_index, hour)

            if current_busyness is not None:
                # Compare current to baseline
                if baseline > 0:
                    ratio = current_busyness / baseline
                else:
                    ratio = 1.0

                # Score: normal = ~50, elevated = 60-80, high = 80+
                if ratio <= 1.0:
                    score = int(50 * ratio)
                    status = 'normal'
                elif ratio <= 1.5:
                    score = int(50 + (ratio - 1.0) * 60)
                    status = 'elevated'
                else:
                    score = min(100, int(80 + (ratio - 1.5) * 40))
                    status = 'high'

                # Late night bonus - unusual activity is more significant
                if is_late_night and current_busyness > 20:
                    score = min(100, score + 15)

                valid_places += 1
                total_score += score

        places_data.append({
            'name': name,
            'current_busyness': current_busyness,
            'baseline': round(baseline, 1),
            'score': score,
            'status': status
        })

    # Calculate aggregate risk
    if valid_places > 0:
        avg_score = total_score / valid_places
    else:
        avg_score = 50

    # Risk contribution (scaled for overall impact)
    risk = int(avg_score * 0.6)  # Pentagon pizza is weighted factor

    # Determine overall status
    if avg_score < 40:
        status = 'Normal'
    elif avg_score < 60:
        status = 'Normal'
    elif avg_score < 80:
        status = 'Elevated'
    else:
        status = 'High'

    return {
        'risk': risk,
        'detail': status,
        'raw_data': {
            'score': round(avg_score, 1),
            'risk_contribution': risk,
            'status': status,
            'places': places_data,
            'timestamp': datetime.utcnow().isoformat(),
            'is_late_night': is_late_night,
            'is_weekend': is_weekend
        }
    }


if __name__ == '__main__':
    import json
    result = get_pentagon_pizza_risk()
    print(json.dumps(result, indent=2))
