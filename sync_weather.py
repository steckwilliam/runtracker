import sys

import requests

from database import (
    ensure_runs_schema,
    get_runs_missing_coordinates,
    get_runs_needing_weather_sync,
    update_run_weather,
)
from historical_weather import get_historical_weather_for_run


def sync_run_weather():
    ensure_runs_schema()

    eligible_runs = get_runs_needing_weather_sync()
    missing_coords = get_runs_missing_coordinates()

    skipped_missing_coords = len(missing_coords)
    updated = 0
    api_failures = 0

    for run in eligible_runs:
        try:
            weather = get_historical_weather_for_run(
                run["start_latitude"],
                run["start_longitude"],
                run["start_datetime_local"],
            )
        except requests.RequestException as exc:
            api_failures += 1
            print(f"Weather API failed for run id {run['id']}: {exc}")
            continue

        if not weather or weather.get("temperature_f") is None:
            api_failures += 1
            print(f"No weather data returned for run id {run['id']} ({run['date']})")
            continue

        update_run_weather(run["id"], weather)
        updated += 1

    print("Weather sync complete")
    print(f"Runs checked for weather: {len(eligible_runs)}")
    print(f"Runs skipped (missing coordinates): {skipped_missing_coords}")
    print(f"Weather records updated: {updated}")
    print(f"API failures: {api_failures}")

    if skipped_missing_coords:
        print(
            "Tip: run `python sync_strava.py` to backfill coordinates for Strava runs."
        )


if __name__ == "__main__":
    try:
        sync_run_weather()
    except requests.RequestException as exc:
        print(f"Weather sync failed: {exc}")
        sys.exit(1)
