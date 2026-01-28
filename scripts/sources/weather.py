"""
Weather Module
Monitors weather conditions over Iran using OpenWeatherMap API.
Clear weather is favorable for air operations = higher risk.

API: OpenWeatherMap Current Weather Data
Docs: https://openweathermap.org/current
"""

import os
import requests
from datetime import datetime

OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY')
BASE_URL = 'https://api.openweathermap.org/data/2.5/weather'

# Key locations in Iran to monitor
# Using multiple points for broader coverage
IRAN_LOCATIONS = [
    {'name': 'Tehran', 'lat': 35.6892, 'lon': 51.3890},
    {'name': 'Isfahan', 'lat': 32.6546, 'lon': 51.6680},
    {'name': 'Natanz', 'lat': 33.5125, 'lon': 51.9164},  # Nuclear facility
    {'name': 'Bushehr', 'lat': 28.9234, 'lon': 50.8203},  # Nuclear plant
]


def fetch_weather(lat, lon):
    """
    Fetch current weather for a location.
    """
    if not OPENWEATHER_API_KEY:
        raise ValueError('OPENWEATHER_API_KEY environment variable not set')

    params = {
        'lat': lat,
        'lon': lon,
        'appid': OPENWEATHER_API_KEY,
        'units': 'metric'
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
    - Precipitation (none = better)
    - Wind speed (moderate = OK)
    """
    score = 0

    # Visibility (in meters, max 10000)
    visibility = weather_data.get('visibility', 10000)
    if visibility >= 10000:
        score += 30  # Excellent visibility
    elif visibility >= 5000:
        score += 20  # Good visibility
    elif visibility >= 1000:
        score += 10  # Marginal
    # else: Poor visibility, no points

    # Cloud cover (percentage)
    clouds = weather_data.get('clouds', {}).get('all', 0)
    if clouds <= 10:
        score += 30  # Clear skies
    elif clouds <= 30:
        score += 20  # Mostly clear
    elif clouds <= 50:
        score += 10  # Partly cloudy
    # else: Overcast, no points

    # Weather condition (main)
    weather = weather_data.get('weather', [{}])[0]
    main_condition = weather.get('main', '').lower()
    description = weather.get('description', '').lower()

    if main_condition in ['clear', 'sunny']:
        score += 30  # Perfect conditions
    elif main_condition == 'clouds' and 'few' in description:
        score += 20
    elif main_condition == 'clouds':
        score += 10
    elif main_condition in ['mist', 'haze']:
        score += 5
    # Rain, snow, thunderstorm = 0 points

    # Wind (moderate is fine, extreme is bad)
    wind_speed = weather_data.get('wind', {}).get('speed', 0)
    if wind_speed <= 10:
        score += 10  # Calm to moderate
    elif wind_speed <= 20:
        score += 5  # Breezy but OK
    # Stronger winds reduce suitability

    return min(100, score)


def get_condition_description(score):
    """
    Get human-readable condition description.
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

        score = calculate_weather_score(weather)
        location_scores.append(score)

        # Extract relevant data
        weather_main = weather.get('weather', [{}])[0]

        location_data.append({
            'name': loc['name'],
            'score': score,
            'temp': weather.get('main', {}).get('temp'),
            'visibility': weather.get('visibility'),
            'clouds': weather.get('clouds', {}).get('all'),
            'description': weather_main.get('description', 'unknown'),
            'condition': get_condition_description(score)
        })

    # Average score across locations
    avg_score = sum(location_scores) / len(location_scores) if location_scores else 50
    risk = int(avg_score)

    # Get overall description from average
    overall_description = get_condition_description(risk)

    return {
        'risk': risk,
        'detail': overall_description,
        'raw_data': {
            'avg_score': round(avg_score, 1),
            'locations': location_data,
            'timestamp': datetime.utcnow().isoformat()
        }
    }


if __name__ == '__main__':
    import json
    result = get_weather_risk()
    print(json.dumps(result, indent=2))
