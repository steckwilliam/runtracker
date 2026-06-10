import requests
from flask import Flask, redirect, render_template, render_template_string, request

from config import Config
from database import (
    get_analysis_data,
    get_best_running_conditions_for_planner,
    get_dashboard_data,
    has_strava_refresh_token,
    init_db,
    save_strava_tokens,
)
from strava_auth import build_authorization_url
from time_of_day import TIME_OF_DAY_BUCKETS, TIME_OF_DAY_METHODOLOGY_LABELS
from weather_service import (
    default_preferences,
    get_recommended_windows,
    parse_preferences,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = Config.FLASK_SECRET_KEY
init_db()


@app.route("/")
def dashboard():
    dashboard_data = get_dashboard_data(request.args.get("range"))
    if app.debug:
        app.logger.debug(
            "Dashboard range=%s runs=%s",
            dashboard_data["range_key"],
            dashboard_data["stats"]["total_runs"],
        )
    return render_template(
        "dashboard.html",
        stats=dashboard_data["stats"],
        recent_runs=dashboard_data["recent_runs"],
        weekly_chart=dashboard_data["weekly_chart"],
        monthly_chart=dashboard_data["monthly_chart"],
        pace_chart=dashboard_data["pace_chart"],
        longest_month_chart=dashboard_data["longest_month_chart"],
        date_range=dashboard_data["range_key"],
        date_range_label=dashboard_data["range_label"],
    )


@app.route("/analysis")
def analysis():
    analysis_data = get_analysis_data(request.args.get("range"))
    return render_template(
        "analysis.html",
        charts=analysis_data,
        date_range=analysis_data["range_key"],
        date_range_label=analysis_data["range_label"],
    )


@app.route("/weather", methods=["GET", "POST"])
def weather():
    best_conditions = get_best_running_conditions_for_planner()
    recommendations = None
    forecast_error = None
    submitted = False

    if request.method == "POST":
        prefs = parse_preferences(request.form)
        submitted = True
    elif _weather_query_has_prefs(request.args):
        prefs = parse_preferences(request.args)
        submitted = True
    else:
        prefs = default_preferences()

    if submitted:
        try:
            recommendations = get_recommended_windows(prefs)
        except requests.RequestException:
            forecast_error = (
                "Could not load the weather forecast. Check your connection and try again."
            )

    return render_template(
        "weather.html",
        prefs=prefs,
        best_conditions=best_conditions,
        recommendations=recommendations,
        forecast_error=forecast_error,
        submitted=submitted,
        time_of_day_methodology=TIME_OF_DAY_METHODOLOGY_LABELS,
        time_of_day_buckets=TIME_OF_DAY_BUCKETS,
    )


def _weather_query_has_prefs(args):
    return any(key in args for key in ("min_temp", "max_temp", "preferred_time"))


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
