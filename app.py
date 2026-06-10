import logging

import requests
from flask import Flask, abort, redirect, render_template, request

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
logger = logging.getLogger(__name__)


@app.context_processor
def inject_public_config():
    return {
        "strava_routes_enabled": Config.ENABLE_STRAVA_ROUTES,
        "weather_location_label": "New Orleans",
    }


@app.route("/")
def dashboard():
    dashboard_data = get_dashboard_data(request.args.get("range"))
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


def _require_strava_routes():
    if not Config.ENABLE_STRAVA_ROUTES:
        abort(404)


@app.route("/strava/status")
def strava_status():
    _require_strava_routes()
    config_status = Config.get_strava_config_status()
    has_connection_token = bool(Config.STRAVA_REFRESH_TOKEN) or has_strava_refresh_token()
    config_status.pop("STRAVA_REFRESH_TOKEN", None)
    config_status["Strava connection token"] = (
        "present" if has_connection_token else "missing"
    )
    return render_template(
        "strava_status.html",
        config_status=config_status,
        has_connection_token=has_connection_token,
    )


@app.route("/strava/connect")
def strava_connect():
    _require_strava_routes()
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
    _require_strava_routes()
    error = request.args.get("error")
    code = request.args.get("code")

    if error:
        return render_template(
            "strava_message.html",
            title="Strava Authorization Failed",
            message=f"Strava returned an error: {error}",
            athlete=None,
        ), 400

    if not code:
        return render_template(
            "strava_message.html",
            title="Strava Authorization Failed",
            message="Missing authorization code. Try connecting again from /strava/connect.",
            athlete=None,
        ), 400

    token_payload = {
        "client_id": Config.STRAVA_CLIENT_ID,
        "client_secret": Config.STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }

    try:
        response = requests.post(Config.STRAVA_TOKEN_URL, data=token_payload, timeout=15)
    except requests.RequestException:
        logger.exception("Strava token request failed")
        return render_template(
            "strava_message.html",
            title="Strava Connection Failed",
            message="Could not reach Strava. Check your connection and try again.",
            athlete=None,
        ), 500

    if response.status_code != 200:
        logger.error("Strava token exchange failed: %s", response.status_code)
        return render_template(
            "strava_message.html",
            title="Strava Connection Failed",
            message="Strava token exchange failed. Check your app credentials in .env.",
            athlete=None,
        ), 500

    token_data = response.json()
    athlete = token_data.get("athlete", {})
    athlete_name = (
        athlete.get("firstname")
        or athlete.get("username")
        or athlete.get("id")
        or "Connected athlete"
    )
    tokens_saved = save_strava_tokens(token_data, request.args.get("scope", ""))

    return render_template(
        "strava_callback.html",
        athlete_name=athlete_name,
        tokens_saved=tokens_saved,
    )


if __name__ == "__main__":
    app.run(debug=True)
