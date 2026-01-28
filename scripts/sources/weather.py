"""
Weather Module
Monitors weather conditions over Iran using Open-Meteo API.
Clear weather is favorable for air operations = higher risk.

API: Open-Meteo Forecast API (free, no API key required)
Docs: https://open-meteo.com/en/docs
"""

import requests
from datetime import datetime, timezone

BASE_URL = 'https://api.open-meteo.com/v1/forecast'

# Key locations in Iran to monitor
IRAN_LOCATIONS = [
    {'name': 'Tehran', 'lat': 35.6892, 'lon': 51.3890},
    {'name': 'Isfahan', 'lat': 32.6546, 'lon': 51.6680},
    {'name': 'Natanz', 'lat': 33.5125, 'lon': 51.9164},  # Nuclear facility
    {'name': 'Bushehr', 'lat': 28.9234, 'lon': 50.8203},  # Nuclear plant
]

# WMO Weather codes (https://open-meteo.com/en/docs)
# 0: Clear sky
# 1-3: Mainly clear, partly cloudy, overcast
# 45, 48: Fog
# 51-55: Drizzle
# 61-65: Rain
# 71-75: Snow
# 80-82: Rain showers
# 95-99: Thunderstorm


def fetch_weather(lat, lon):
    """
    Fetch current weather for a location using Open-Meteo.
    No API key required.
    """
    params = {
        'latitude': lat,
        'longitude': lon,
        'current': 'temperature_2m,weather_code,cloud_cover,visibility,wind_speed_10m'
    }

    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


def calculate_weather_score(weather_data):
    """
    Calculate a weather score for air operations feasibility.
    Higher score = better conditions for operations = higher risk.

    Factors:
    - Visibility (higher = better)
    - Cloud cover (lower = better)
    - Weather code (clear = better)
    - Wind speed (moderate = OK)
    """
    current = weather_data.get('current', {})
    score = 0

    # Visibility (in meters)
    visibility = current.get('visibility', 10000)
    if visibility >= 50000:
        score += 30  # Excellent visibility
    elif visibility >= 20000:
        score += 25  # Very good
    elif visibility >= 10000:
        score += 20  # Good visibility
    elif visibility >= 5000:
        score += 10  # Marginal
    # else: Poor visibility, no points

    # Cloud cover (percentage)
    clouds = current.get('cloud_cover', 0)
    if clouds <= 10:
        score += 30  # Clear skies
    elif clouds <= 30:
        score += 25  # Mostly clear
    elif clouds <= 50:
        score += 15  # Partly cloudy
    elif clouds <= 75:
        score += 5   # Mostly cloudy
    # else: Overcast, no points

    # Weather code
    weather_code = current.get('weather_code', 0)
    if weather_code == 0:
        score += 30  # Clear sky - perfect
    elif weather_code <= 3:
        score += 20  # Mainly clear to overcast
    elif weather_code in [45, 48]:
        score += 5   # Fog - poor
    # Rain, snow, thunderstorm = 0 points

    # Wind (moderate is fine, extreme is bad)
    wind_speed = current.get('wind_speed_10m', 0)
    if wind_speed <= 20:
        score += 10  # Calm to moderate
    elif wind_speed <= 40:
        score += 5   # Breezy but OK
    # Stronger winds reduce suitability

    return min(100, score)


def get_weather_description(weather_code):
    """
    Get human-readable description from WMO weather code.
    """
    descriptions = {
        0: 'clear sky',
        1: 'mainly clear',
        2: 'partly cloudy',
        3: 'overcast',
        45: 'fog',
        48: 'depositing rime fog',
        51: 'light drizzle',
        53: 'moderate drizzle',
        55: 'dense drizzle',
        61: 'slight rain',
        63: 'moderate rain',
        65: 'heavy rain',
        71: 'slight snow',
        73: 'moderate snow',
        75: 'heavy snow',
        80: 'slight rain showers',
        81: 'moderate rain showers',
        82: 'violent rain showers',
        95: 'thunderstorm',
        96: 'thunderstorm with slight hail',
        99: 'thunderstorm with heavy hail',
    }
    return descriptions.get(weather_code, 'unknown')


def get_condition_label(score):
    """
    Get human-readable condition label.
    """
    if score >= 80:
        return 'clear'
    elif score >= 60:
        return 'favorable'
    elif score >= 40:
        return 'marginal'
    else:
        return 'poor'


def get_weather_risk():
    """
    Get weather conditions over Iran and calculate risk score.
    Better weather = higher risk (favorable for air operations).
    """
    location_scores = []
    location_data = []

    for loc in IRAN_LOCATIONS:
        weather = fetch_weather(loc['lat'], loc['lon'])
        current = weather.get('current', {})

        score = calculate_weather_score(weather)
        location_scores.append(score)

        weather_code = current.get('weather_code', 0)

        location_data.append({
            'name': loc['name'],
            'score': score,
            'temp': current.get('temperature_2m'),
            'visibility': current.get('visibility'),
            'clouds': current.get('cloud_cover'),
            'wind_speed': current.get('wind_speed_10m'),
            'weather_code': weather_code,
            'description': get_weather_description(weather_code),
            'condition': get_condition_label(score)
        })

    # Average score across locations
    avg_score = sum(location_scores) / len(location_scores) if location_scores else 50
    risk = int(avg_score)

    # Get overall description from average
    overall_description = get_condition_label(risk)

    return {
        'risk': risk,
        'detail': overall_description,
        'raw_data': {
            'avg_score': round(avg_score, 1),
            'locations': location_data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    }


if __name__ == '__main__':
    import json
    result = get_weather_risk()
    print(json.dumps(result, indent=2))
