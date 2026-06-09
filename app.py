import requests
from flask import Flask, redirect, render_template, render_template_string, request

from config import Config
from database import (
    get_dashboard_stats,
    get_monthly_mileage_data,
    get_pace_trend_data,
    get_recent_runs,
    get_weekly_mileage_data,
    has_strava_refresh_token,
    init_db,
    save_strava_tokens,
)
from strava_auth import build_authorization_url

app = Flask(__name__)
app.config["SECRET_KEY"] = Config.FLASK_SECRET_KEY
init_db()


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        stats=get_dashboard_stats(),
        recent_runs=get_recent_runs(),
        weekly_chart=get_weekly_mileage_data(),
        monthly_chart=get_monthly_mileage_data(),
        pace_chart=get_pace_trend_data(),
    )


@app.route("/weather")
def weather():
    return render_template("weather.html")


@app.route("/strava/status")
def strava_status():
    config_status = Config.get_strava_config_status()
    has_connection_token = bool(Config.STRAVA_REFRESH_TOKEN) or has_strava_refresh_token()
    config_status.pop("STRAVA_REFRESH_TOKEN", None)
    config_status["Strava connection token"] = (
        "present" if has_connection_token else "missing"
    )
    return render_template(
        "strava_status.html",
        config_status=config_status,
    )


@app.route("/strava/connect")
def strava_connect():
    missing = Config.get_missing_strava_connect_vars()
    if missing:
        return render_template(
            "strava_message.html",
            title="Strava Not Configured",
            message=(
                "Add the following to your local .env file before connecting: "
                + ", ".join(missing)
            ),
            athlete=None,
        )

    return redirect(build_authorization_url())


@app.route("/strava/callback")
def strava_callback():
    error = request.args.get("error")
    code = request.args.get("code")
    scope = request.args.get("scope", "")

    if error:
        return f"Strava authorization failed: {error}", 400

    if not code:
        return "Missing Strava authorization code.", 400

    print("Strava callback received")
    print(f"Authorization code present: {bool(code)}")
    print(f"Accepted scopes: {scope}")

    token_payload = {
        "client_id": Config.STRAVA_CLIENT_ID,
        "client_secret": Config.STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }

    try:
        response = requests.post(Config.STRAVA_TOKEN_URL, data=token_payload, timeout=15)
    except requests.RequestException as exc:
        print(f"Strava token request failed: {exc}")
        return "Strava token request failed. Check the terminal for details.", 500

    if response.status_code != 200:
        print(f"Strava token exchange failed with status {response.status_code}")
        print(response.text)
        return (
            f"Strava token exchange failed with status {response.status_code}. "
            "Check terminal output."
        ), 500

    token_data = response.json()

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    athlete = token_data.get("athlete", {})

    athlete_name = (
        athlete.get("firstname")
        or athlete.get("username")
        or athlete.get("id")
        or "Unknown"
    )

    tokens_saved = save_strava_tokens(token_data, scope)

    print("Strava connected successfully")
    print(f"Accepted scopes: {scope}")
    print(f"Access token received: {'Yes' if access_token else 'No'}")
    print(f"Refresh token received: {'Yes' if refresh_token else 'No'}")
    print(f"Tokens saved to database: {'Yes' if tokens_saved else 'No'}")
    print(f"Athlete: {athlete_name}")

    return render_template_string(
        """
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Strava Connected</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="bg-light">
            <main class="container py-5">
                <div class="card shadow-sm border-0 rounded-4">
                    <div class="card-body p-4">
                        <h1 class="h3 mb-3">Connected to Strava successfully</h1>

                        <p><strong>Accepted scopes:</strong> {{ scope }}</p>
                        <p><strong>Access token received:</strong> {{ "Yes" if access_token else "No" }}</p>
                        <p><strong>Refresh token received:</strong> {{ "Yes" if refresh_token else "No" }}</p>
                        <p><strong>Tokens saved to database:</strong> {{ "Yes" if tokens_saved else "No" }}</p>
                        <p><strong>Athlete:</strong> {{ athlete_name }}</p>

                        <div class="alert alert-info mt-4">
                            Tokens were not shown in the browser for security.
                            Next step: visit <a href="/strava/status">/strava/status</a> to confirm your Strava connection token is Present.
                        </div>

                        <a href="/strava/status" class="btn btn-primary">Check Strava Status</a>
                        <a href="/" class="btn btn-outline-secondary ms-2">Back to Dashboard</a>
                    </div>
                </div>
            </main>
        </body>
        </html>
        """,
        scope=scope,
        access_token=access_token,
        refresh_token=refresh_token,
        tokens_saved=tokens_saved,
        athlete_name=athlete_name,
    )


if __name__ == "__main__":
    app.run(debug=True)
