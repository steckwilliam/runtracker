import sys

import requests

from config import Config
from database import (
    ensure_runs_schema,
    extract_run_time_fields,
    get_strava_tokens,
    insert_strava_run,
    seconds_to_pace,
    update_strava_tokens_from_refresh,
)

STRAVA_API_BASE = "https://www.strava.com/api/v3"
METERS_PER_MILE = 1609.344
RUN_SPORT_TYPES = {"Run", "TrailRun", "VirtualRun"}


def format_moving_time(total_seconds):
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def get_refresh_token():
    tokens = get_strava_tokens()
    if tokens and tokens.get("refresh_token"):
        return tokens["refresh_token"]
    return Config.STRAVA_REFRESH_TOKEN or None


def refresh_access_token(refresh_token):
    response = requests.post(
        Config.STRAVA_TOKEN_URL,
        data={
            "client_id": Config.STRAVA_CLIENT_ID,
            "client_secret": Config.STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    if not response.ok:
        print(f"Strava token refresh failed with status {response.status_code}")
        print(response.text)
        sys.exit(1)

    token_data = response.json()
    update_strava_tokens_from_refresh(token_data)
    return token_data["access_token"]


def fetch_activities(access_token, max_pages=4, per_page=50):
    activities = []
    headers = {"Authorization": f"Bearer {access_token}"}

    for page in range(1, max_pages + 1):
        response = requests.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers=headers,
            params={"per_page": per_page, "page": page},
            timeout=30,
        )
        if not response.ok:
            print(f"Strava activities request failed with status {response.status_code}")
            print(response.text)
            sys.exit(1)

        page_activities = response.json()
        if not page_activities:
            break
        activities.extend(page_activities)

    return activities


def is_run_activity(activity):
    activity_type = activity.get("type", "")
    sport_type = activity.get("sport_type", "")
    return activity_type == "Run" or sport_type in RUN_SPORT_TYPES


def map_strava_activity_to_run(activity):
    distance_m = activity.get("distance") or 0
    moving_time_s = int(activity.get("moving_time") or 0)
    distance_miles = distance_m / METERS_PER_MILE

    if distance_miles > 0 and moving_time_s > 0:
        pace_seconds = round(moving_time_s / distance_miles)
    else:
        pace_seconds = 0

    start_local = activity.get("start_date_local") or activity.get("start_date", "")
    date = start_local[:10]
    time_fields = extract_run_time_fields(start_local)

    elevation = activity.get("total_elevation_gain")
    elevation_gain = int(round(elevation)) if elevation else None

    return {
        "strava_activity_id": str(activity["id"]),
        "date": date,
        "name": activity.get("name") or "Run",
        "distance_miles": round(distance_miles, 2),
        "pace_per_mile": seconds_to_pace(pace_seconds),
        "pace_seconds": pace_seconds,
        "moving_time": format_moving_time(moving_time_s),
        "elevation_gain": elevation_gain,
        "run_type": activity.get("sport_type") or activity.get("type") or "Run",
        **time_fields,
    }


def sync_strava_runs():
    ensure_runs_schema()

    if not Config.STRAVA_CLIENT_ID or not Config.STRAVA_CLIENT_SECRET:
        print("Missing STRAVA_CLIENT_ID or STRAVA_CLIENT_SECRET in .env")
        sys.exit(1)

    refresh_token = get_refresh_token()
    if not refresh_token:
        print("No Strava refresh token found. Connect via /strava/connect first.")
        sys.exit(1)

    access_token = refresh_access_token(refresh_token)
    activities = fetch_activities(access_token)

    run_activities = [a for a in activities if is_run_activity(a)]

    inserted = 0
    backfilled = 0
    skipped = 0
    for activity in run_activities:
        run_data = map_strava_activity_to_run(activity)
        result = insert_strava_run(run_data)
        if result == "inserted":
            inserted += 1
        elif result == "backfilled":
            backfilled += 1
        else:
            skipped += 1

    print("Strava sync complete")
    print(f"Activities fetched: {len(activities)}")
    print(f"Run activities found: {len(run_activities)}")
    print(f"New runs inserted: {inserted}")
    print(f"Existing runs backfilled with start time: {backfilled}")
    print(f"Duplicates skipped: {skipped}")


if __name__ == "__main__":
    sync_strava_runs()
