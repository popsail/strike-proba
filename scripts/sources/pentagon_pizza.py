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
from datetime import datetime, timezone

OUTSCRAPER_API_KEY = os.environ.get('OUTSCRAPER_API_KEY')
BASE_URL = 'https://api.app.outscraper.com/maps/search-v3'

# Pizza places near Pentagon to monitor (by place_id for reliable results)
# These are pizza places in Pentagon City/Crystal City, Arlington VA
PENTAGON_PIZZA_PLACES = [
    'ChIJv3hqkuW3t4kRjuvLKz6arZI',  # Wiseguy Pizza, 710 12th St S
    'ChIJS1rpOC-3t4kRsLyM6aftM8k',  # We, The Pizza, 2110 Crystal Dr
    'ChIJ7y7tKd-2t4kRVQLgS4v63A4',  # California Pizza Kitchen, 1201 S Hayes St
    'ChIJcYireCe3t4kR4d9trEbGYjc',  # Extreme Pizza, 1419 S Fern St
    'ChIJ42QeLXu3t4kRnArvcaz2o3A',  # District Pizza Palace, 2325 S Eads St
]

# Day indices (Monday = 0)
DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def fetch_place_data(place_id, retries=3):
    """
    Fetch place data including popular times from Outscraper by place_id.
    Retries on timeout/connection errors.
    """
    if not OUTSCRAPER_API_KEY:
        raise ValueError('OUTSCRAPER_API_KEY environment variable not set')

    headers = {
        'X-API-KEY': OUTSCRAPER_API_KEY
    }

    params = {
        'query': place_id,
        'limit': 1,
        'async': 'false'
    }

    last_error = None
    for attempt in range(retries):
        try:
            response = requests.get(BASE_URL, params=params, headers=headers, timeout=90)
            response.raise_for_status()
            # Outscraper returns {"data": [[{place}]]}
            data = response.json()
            return data['data'][0][0]
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e

    raise last_error


def get_live_busyness(popular_times):
    """
    Get live busyness from popular_times data.
    API returns {'day': 'live', 'percentage': N, 'title': '...'} entry.
    """
    for entry in popular_times:
        if entry.get('day') == 'live':
            return entry['percentage']
    return None


def get_historical_busyness(popular_times, day_index, hour):
    """
    Get historical busyness for specific day/hour.
    API structure: {'day': 1-7, 'popular_times': [{'hour': N, 'percentage': X}, ...]}
    Python weekday: 0=Mon...6=Sun -> API day: 1=Mon...7=Sun
    """
    api_day = day_index + 1  # Convert Python weekday to API day

    for entry in popular_times:
        if entry.get('day') == api_day:
            for hour_data in entry['popular_times']:
                if hour_data['hour'] == hour:
                    return hour_data['percentage']
    return None


def get_baseline_busyness(popular_times, hour):
    """
    Get average busyness for this hour across all days (baseline).
    If hour doesn't exist (e.g., late night when closed), use overall average.
    """
    hour_total = 0
    hour_count = 0
    all_total = 0
    all_count = 0

    for entry in popular_times:
        if entry.get('day') == 'live':
            continue
        for hour_data in entry['popular_times']:
            if hour_data['percentage'] > 0:
                all_total += hour_data['percentage']
                all_count += 1
                if hour_data['hour'] == hour:
                    hour_total += hour_data['percentage']
                    hour_count += 1

    # Prefer specific hour average, fallback to overall average
    if hour_count > 0:
        return hour_total / hour_count
    elif all_count > 0:
        return all_total / all_count
    return None


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

    for place_id in PENTAGON_PIZZA_PLACES:
        place = fetch_place_data(place_id)

        name = place['name']
        popular_times = place.get('popular_times')

        if not popular_times:
            continue

        # Try live data first, fall back to historical
        current_busyness = get_live_busyness(popular_times)
        if current_busyness is None:
            current_busyness = get_historical_busyness(popular_times, day_index, hour)
        baseline = get_baseline_busyness(popular_times, hour)

        if current_busyness is None or baseline is None:
            continue

        # Compare current to baseline
        ratio = current_busyness / baseline

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
    if valid_places == 0:
        raise ValueError('No valid popular_times data from any pizza place')

    avg_score = total_score / valid_places

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
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'is_late_night': is_late_night,
            'is_weekend': is_weekend
        }
    }


if __name__ == '__main__':
    import json
    result = get_pentagon_pizza_risk()
    print(json.dumps(result, indent=2))
