from urllib.parse import urlencode

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
