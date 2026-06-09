from flask import Flask, render_template

from database import (
    get_dashboard_stats,
    get_monthly_mileage_data,
    get_pace_trend_data,
    get_recent_runs,
    get_weekly_mileage_data,
)

app = Flask(__name__)


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


if __name__ == "__main__":
    app.run(debug=True)
