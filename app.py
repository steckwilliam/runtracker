import logging

import requests
from flask import Flask, abort, redirect, render_template, request, url_for

from config import Config
from database import (
    get_analysis_data,
    get_best_running_conditions_for_planner,
    get_dashboard_data,
    get_shoe_tracker_data,
    has_strava_refresh_token,
    init_db,
    save_strava_tokens,
    set_active_shoe,
)
from strava_auth import build_authorization_url
from time_of_day import TIME_OF_DAY_BUCKETS, TIME_OF_DAY_METHODOLOGY_LABELS
from weekly_planner_service import (
    build_weekly_plan,
    default_weekly_plan_preferences,
    get_runs_per_week_choices,
    get_target_pace_choices,
    get_weekly_mileage_choices,
    parse_weekly_plan_preferences,
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
        shoe_tracker=get_shoe_tracker_data(),
        shoe_error=request.args.get("shoe_error"),
    )


@app.route("/dashboard/shoe", methods=["POST"])
def dashboard_shoe():
    range_key = request.form.get("range") or request.args.get("range")
    name = request.form.get("name", "")
    start_date = request.form.get("start_date", "")

    try:
        set_active_shoe(name, start_date)
    except ValueError as exc:
        return redirect(_dashboard_shoe_redirect(range_key, shoe_error=str(exc)), code=303)

    return redirect(_dashboard_shoe_redirect(range_key), code=303)


def _dashboard_shoe_redirect(range_key=None, shoe_error=None):
    params = {}
    if range_key:
        params["range"] = range_key
    if shoe_error:
        params["shoe_error"] = shoe_error
    base = url_for("dashboard", **params) if params else url_for("dashboard")
    return f"{base}#shoe-tracker"


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
@app.route("/run-planner", methods=["GET", "POST"])
def weather():
    best_conditions = get_best_running_conditions_for_planner()
    weekly_mileage_choices, typical_weekly_miles = get_weekly_mileage_choices()
    runs_per_week_choices, typical_runs_per_week, average_runs_per_week = get_runs_per_week_choices()
    target_pace_choices, default_target_pace_seconds = get_target_pace_choices()

    weekly_plan = None
    forecast_error = None
    week_submitted = False
    week_prefs = default_weekly_plan_preferences()

    if request.method == "POST":
        week_prefs = parse_weekly_plan_preferences(request.form)
        week_submitted = True
        try:
            weekly_plan = build_weekly_plan(week_prefs)
        except requests.RequestException:
            forecast_error = (
                "Could not load the weather forecast. Check your connection and try again."
            )
    elif _run_planner_query_has_prefs(request.args):
        week_prefs = parse_weekly_plan_preferences(request.args)
        week_submitted = True
        try:
            weekly_plan = build_weekly_plan(week_prefs)
        except requests.RequestException:
            forecast_error = (
                "Could not load the weather forecast. Check your connection and try again."
            )

    return render_template(
        "weather.html",
        week_prefs=week_prefs,
        best_conditions=best_conditions,
        weekly_plan=weekly_plan,
        weekly_mileage_choices=weekly_mileage_choices,
        runs_per_week_choices=runs_per_week_choices,
        target_pace_choices=target_pace_choices,
        typical_weekly_miles=typical_weekly_miles,
        typical_runs_per_week=typical_runs_per_week,
        average_runs_per_week=average_runs_per_week,
        default_target_pace_seconds=default_target_pace_seconds,
        forecast_error=forecast_error,
        week_submitted=week_submitted,
        time_of_day_methodology=TIME_OF_DAY_METHODOLOGY_LABELS,
        time_of_day_buckets=TIME_OF_DAY_BUCKETS,
    )


def _run_planner_query_has_prefs(args):
    return any(
        key in args
        for key in (
            "min_temp",
            "max_temp",
            "preferred_time",
            "runs_per_week",
            "weekly_miles",
            "target_pace",
        )
    )


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
