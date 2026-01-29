#!/usr/bin/env python3
"""
Main data aggregation script.
Fetches data from all sources, calculates total risk, and writes to data.json.

NO FALLBACK DATA - if any API fails, this script will exit with an error.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add sources directory to path
sys.path.insert(0, str(Path(__file__).parent / 'sources'))

from sources.news import get_news_risk
from sources.aviation import get_aviation_risk
from sources.tankers import get_tanker_risk
from sources.pentagon_pizza import get_pentagon_pizza_risk
from sources.polymarket import get_polymarket_risk
from sources.weather import get_weather_risk

# Output file path (relative to repo root)
OUTPUT_FILE = Path(__file__).parent.parent / 'data.json'

# History length for rolling arrays
HISTORY_LENGTH = 17

# Signal weights for total risk calculation (research-justified)
# Polymarket: 40% - only externally-validated metric (67-94% accuracy)
# Aviation: 20% - rolling baseline + strong signal when NOTAMs present
# Tankers: 15% - rolling baseline, but unreliable callsign detection
# News: 10% - GDELT % of global coverage, reduced weight (noisy)
# Pentagon: 10% - historical precedent documented (Wikipedia)
# Weather: 5% - FM 34-81-1 operational but not predictive
WEIGHTS = {
    'polymarket': 0.40,
    'aviation': 0.20,
    'tanker': 0.15,
    'news': 0.10,
    'pentagon': 0.10,
    'weather': 0.05,
}

# Rolling baseline history lengths
AVIATION_HISTORY_LENGTH = 144  # 24 hours at 10-min intervals
TANKER_HISTORY_LENGTH = 1008   # 7 days at 10-min intervals


def load_existing_data():
    """
    Load existing data.json if it exists.
    """
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def update_history(existing_history, new_value, max_length=HISTORY_LENGTH):
    """
    Add new value to history array, maintaining max length.
    """
    if existing_history is None:
        existing_history = []

    history = list(existing_history)
    history.append(new_value)

    # Trim to max length (keep most recent)
    if len(history) > max_length:
        history = history[-max_length:]

    return history


def update_trend_history(existing_history, new_risk, timestamp_ms):
    """
    Update the 72-hour trend history.
    Pins hourly entries for the chart.
    """
    if existing_history is None:
        existing_history = []

    history = list(existing_history)

    # Check if we should pin this entry (once per hour)
    should_pin = True
    if history:
        last_pinned = next((h for h in reversed(history) if h.get('pinned')), None)
        if last_pinned:
            last_timestamp = last_pinned.get('timestamp', 0)
            # Pin if more than 50 minutes since last pin
            if timestamp_ms - last_timestamp < 50 * 60 * 1000:
                should_pin = False

    # Add new entry
    entry = {
        'timestamp': timestamp_ms,
        'risk': new_risk,
    }
    if should_pin:
        entry['pinned'] = True

    history.append(entry)

    # Keep only last 72 hours of pinned entries + recent non-pinned
    # ~72 pinned entries + some recent ones
    max_entries = 80

    if len(history) > max_entries:
        # Keep all pinned entries from last 72 hours and recent entries
        cutoff_ms = timestamp_ms - (72 * 60 * 60 * 1000)
        filtered = [h for h in history if h.get('pinned') and h.get('timestamp', 0) > cutoff_ms]
        # Add most recent entries if not enough
        recent = [h for h in history[-10:] if h not in filtered]
        history = filtered + recent

    return history


def calculate_total_risk(signals):
    """
    Calculate weighted total risk from all signals.
    """
    total = 0
    weight_sum = 0

    for key, weight in WEIGHTS.items():
        if key in signals and 'risk' in signals[key]:
            total += signals[key]['risk'] * weight
            weight_sum += weight

    if weight_sum > 0:
        return int(total / weight_sum * (sum(WEIGHTS.values()) / weight_sum))

    return 0


def count_elevated_signals(signals, threshold=50):
    """
    Count how many signals are above the elevated threshold.
    """
    count = 0
    for key in WEIGHTS.keys():
        if key in signals and signals[key].get('risk', 0) >= threshold:
            count += 1
    return count


def main():
    """
    Main execution: fetch all data, aggregate, and write to data.json.
    """
    print('Starting data update...')

    # Load existing data for history
    existing = load_existing_data()

    # Fetch all signals - NO TRY/EXCEPT, let errors propagate
    print('Fetching news data...')
    news = get_news_risk()
    print(f'  News risk: {news["risk"]}')

    # Get rolling baseline histories for aviation and tankers
    aviation_baseline = []
    tanker_baseline = []
    if existing:
        aviation_baseline = existing.get('aviation', {}).get('raw_data', {}).get('baseline_history', [])
        tanker_baseline = existing.get('tanker', {}).get('raw_data', {}).get('baseline_history', [])

    print('Fetching aviation data...')
    aviation = get_aviation_risk(history=aviation_baseline)
    print(f'  Aviation risk: {aviation["risk"]}')

    print('Fetching tanker data...')
    tanker = get_tanker_risk(history=tanker_baseline)
    print(f'  Tanker risk: {tanker["risk"]}')

    print('Fetching Pentagon pizza data...')
    pentagon = get_pentagon_pizza_risk()
    print(f'  Pentagon risk: {pentagon["risk"]}')

    print('Fetching Polymarket data...')
    polymarket = get_polymarket_risk()
    print(f'  Polymarket risk: {polymarket["risk"]}')

    print('Fetching weather data...')
    weather = get_weather_risk()
    print(f'  Weather risk: {weather["risk"]}')

    # Build signals dict
    signals = {
        'news': news,
        'aviation': aviation,
        'tanker': tanker,
        'pentagon': pentagon,
        'polymarket': polymarket,
        'weather': weather,
    }

    # Update display histories (for sparkline charts)
    for key in signals:
        existing_history = None
        if existing and key in existing:
            existing_history = existing[key].get('history')
        signals[key]['history'] = update_history(existing_history, signals[key]['risk'])

    # Update rolling baseline histories for aviation and tankers
    # Aviation: store total_count for 24-hour baseline
    aviation_count = aviation['raw_data'].get('total_count', 0)
    new_aviation_baseline = update_history(aviation_baseline, aviation_count, AVIATION_HISTORY_LENGTH)
    aviation['raw_data']['baseline_history'] = new_aviation_baseline

    # Tankers: store tanker_count for 7-day baseline
    tanker_count = tanker['raw_data'].get('tanker_count', 0)
    new_tanker_baseline = update_history(tanker_baseline, tanker_count, TANKER_HISTORY_LENGTH)
    tanker['raw_data']['baseline_history'] = new_tanker_baseline

    # Calculate total risk
    total_risk = calculate_total_risk(signals)
    elevated_count = count_elevated_signals(signals)

    print(f'Total risk: {total_risk}')
    print(f'Elevated signals: {elevated_count}')

    # Update trend history
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    existing_trend = None
    if existing and 'total_risk' in existing:
        existing_trend = existing['total_risk'].get('history')

    trend_history = update_trend_history(existing_trend, total_risk, timestamp_ms)

    # Build final output
    output = {
        **signals,
        'total_risk': {
            'risk': total_risk,
            'history': trend_history,
            'elevated_count': elevated_count,
        },
        'last_updated': datetime.now(timezone.utc).isoformat(),
    }

    # Write to file
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    print(f'Data written to {OUTPUT_FILE}')
    print('Update complete.')


if __name__ == '__main__':
    main()
