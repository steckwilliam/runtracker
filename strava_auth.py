from urllib.parse import urlencode

import requests

from config import Config


def build_authorization_url():
    params = {
        "client_id": Config.STRAVA_CLIENT_ID,
        "redirect_uri": Config.STRAVA_REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "force",
        "scope": "read,activity:read_all",
    }
    return f"{Config.STRAVA_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code):
    response = requests.post(
        Config.STRAVA_TOKEN_URL,
        data={
            "client_id": Config.STRAVA_CLIENT_ID,
            "client_secret": Config.STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )

    if not response.ok:
        return None, f"Strava token exchange failed (HTTP {response.status_code})."

    data = response.json()
    refresh_token = data.get("refresh_token")
    if refresh_token:
        print(
            "\n[RunTracker] Strava refresh token received. "
            "Add this to your local .env file:\n"
            f"STRAVA_REFRESH_TOKEN={refresh_token}\n"
        )

    athlete = data.get("athlete") or {}
    return athlete, None
