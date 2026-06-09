import calendar
from datetime import datetime, timedelta

from flask import Flask, render_template

app = Flask(__name__)

SAMPLE_RUNS = [
    {
        "date": "2026-06-08",
        "name": "Evening Run",
        "distance_miles": 4.6,
        "pace_per_mile": "9:39",
        "moving_time": "44:40",
        "elevation_gain": 38,
        "run_type": "Easy",
    },
    {
        "date": "2026-06-06",
        "name": "Easy Run",
        "distance_miles": 3.2,
        "pace_per_mile": "9:22",
        "moving_time": "29:58",
        "elevation_gain": 22,
        "run_type": "Easy",
    },
    {
        "date": "2026-06-04",
        "name": "Morning Run",
        "distance_miles": 5.1,
        "pace_per_mile": "9:48",
        "moving_time": "49:58",
        "elevation_gain": 45,
        "run_type": "Easy",
    },
    {
        "date": "2026-06-02",
        "name": "Recovery Run",
        "distance_miles": 2.8,
        "pace_per_mile": "10:05",
        "moving_time": "28:14",
        "elevation_gain": 15,
        "run_type": "Recovery",
    },
    {
        "date": "2026-05-29",
        "name": "Tempo Run",
        "distance_miles": 4.0,
        "pace_per_mile": "8:45",
        "moving_time": "35:00",
        "elevation_gain": 52,
        "run_type": "Tempo",
    },
    {
        "date": "2026-05-25",
        "name": "Long Run",
        "distance_miles": 8.4,
        "pace_per_mile": "9:55",
        "moving_time": "1:23:18",
        "elevation_gain": 210,
        "run_type": "Long",
    },
    {
        "date": "2026-05-20",
        "name": "Park Loop",
        "distance_miles": 3.5,
        "pace_per_mile": "9:30",
        "moving_time": "33:15",
        "elevation_gain": 28,
        "run_type": "Easy",
    },
    {
        "date": "2026-05-15",
        "name": "Hill Repeats",
        "distance_miles": 4.2,
        "pace_per_mile": "9:10",
        "moving_time": "38:42",
        "elevation_gain": 185,
        "run_type": "Tempo",
    },
    {
        "date": "2026-05-08",
        "name": "Easy Run",
        "distance_miles": 3.8,
        "pace_per_mile": "9:45",
        "moving_time": "37:06",
        "elevation_gain": 30,
        "run_type": "Easy",
    },
    {
        "date": "2026-04-28",
        "name": "Long Run",
        "distance_miles": 7.2,
        "pace_per_mile": "10:02",
        "moving_time": "1:12:14",
        "elevation_gain": 165,
        "run_type": "Long",
    },
    {
        "date": "2026-04-18",
        "name": "Morning Run",
        "distance_miles": 4.5,
        "pace_per_mile": "9:28",
        "moving_time": "42:36",
        "elevation_gain": 40,
        "run_type": "Easy",
    },
    {
        "date": "2026-04-10",
        "name": "Recovery Run",
        "distance_miles": 2.5,
        "pace_per_mile": "10:15",
        "moving_time": "25:38",
        "elevation_gain": 12,
        "run_type": "Recovery",
    },
    {
        "date": "2026-03-22",
        "name": "Tempo Run",
        "distance_miles": 5.0,
        "pace_per_mile": "8:52",
        "moving_time": "44:20",
        "elevation_gain": 48,
        "run_type": "Tempo",
    },
    {
        "date": "2026-03-10",
        "name": "Easy Run",
        "distance_miles": 3.6,
        "pace_per_mile": "9:55",
        "moving_time": "35:42",
        "elevation_gain": 25,
        "run_type": "Easy",
    },
]


def pace_to_seconds(pace_str):
    minutes, seconds = pace_str.split(":")
    return int(minutes) * 60 + int(seconds)


def seconds_to_pace(total_seconds):
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def format_date_label(dt):
    return f"{calendar.month_abbr[dt.month]} {dt.day}"


def format_month_label(dt):
    return calendar.month_abbr[dt.month]


def format_date_short(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return format_date_label(dt)


def enrich_run_for_display(run):
    return {
        **run,
        "date_display": format_date_short(run["date"]),
        "distance_display": f"{run['distance_miles']:.1f} mi",
        "pace_display": f"{run['pace_per_mile']} /mi",
    }


def get_summary_stats(runs):
    total_miles = sum(r["distance_miles"] for r in runs)
    now = datetime(2026, 6, 9)
    runs_this_month = sum(
        1
        for r in runs
        if datetime.strptime(r["date"], "%Y-%m-%d").month == now.month
        and datetime.strptime(r["date"], "%Y-%m-%d").year == now.year
    )
    avg_pace_seconds = round(
        sum(pace_to_seconds(r["pace_per_mile"]) for r in runs) / len(runs)
    )
    longest = max(r["distance_miles"] for r in runs)
    return {
        "total_miles": f"{total_miles:.1f} mi",
        "runs_this_month": runs_this_month,
        "average_pace": f"{seconds_to_pace(avg_pace_seconds)} /mi",
        "longest_run": f"{longest:.1f} mi",
    }


def _week_start(dt):
    return dt - timedelta(days=dt.weekday())


def get_weekly_mileage(runs):
    week_totals = {}
    for run in runs:
        dt = datetime.strptime(run["date"], "%Y-%m-%d")
        week_key = _week_start(dt)
        week_totals[week_key] = week_totals.get(week_key, 0) + run["distance_miles"]

    sorted_weeks = sorted(week_totals.keys())
    if len(sorted_weeks) > 8:
        sorted_weeks = sorted_weeks[-8:]

    labels = [format_date_label(wk) for wk in sorted_weeks]
    values = [round(week_totals[wk], 1) for wk in sorted_weeks]
    return {"labels": labels, "values": values}


def get_monthly_mileage(runs):
    month_totals = {}
    for run in runs:
        dt = datetime.strptime(run["date"], "%Y-%m-%d")
        month_key = dt.replace(day=1)
        month_totals[month_key] = month_totals.get(month_key, 0) + run["distance_miles"]

    sorted_months = sorted(month_totals.keys())
    if len(sorted_months) > 6:
        sorted_months = sorted_months[-6:]

    labels = [format_month_label(m) for m in sorted_months]
    values = [round(month_totals[m], 1) for m in sorted_months]
    return {"labels": labels, "values": values}


def get_pace_trend(runs):
    week_paces = {}
    for run in runs:
        dt = datetime.strptime(run["date"], "%Y-%m-%d")
        week_key = _week_start(dt)
        week_paces.setdefault(week_key, []).append(pace_to_seconds(run["pace_per_mile"]))

    sorted_weeks = sorted(week_paces.keys())
    labels = [format_date_label(wk) for wk in sorted_weeks]
    values = [round(sum(paces) / len(paces)) for paces in [week_paces[wk] for wk in sorted_weeks]]
    return {"labels": labels, "values": values}


@app.route("/")
def dashboard():
    sorted_runs = sorted(SAMPLE_RUNS, key=lambda r: r["date"], reverse=True)
    recent_runs = [enrich_run_for_display(r) for r in sorted_runs]
    return render_template(
        "dashboard.html",
        stats=get_summary_stats(SAMPLE_RUNS),
        recent_runs=recent_runs,
        weekly_chart=get_weekly_mileage(SAMPLE_RUNS),
        monthly_chart=get_monthly_mileage(SAMPLE_RUNS),
        pace_chart=get_pace_trend(SAMPLE_RUNS),
    )


@app.route("/weather")
def weather():
    return render_template("weather.html")


if __name__ == "__main__":
    app.run(debug=True)
