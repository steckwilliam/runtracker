# RunTracker

A personal running analytics dashboard using Strava activity data and historical weather data.

RunTracker syncs your runs locally, surfaces training trends on a filterable dashboard, analyzes performance by temperature and time of day, and recommends future run windows based on your recent aggregate pace patterns.

## Features

- **Strava OAuth connection** — connect your account without committing tokens to Git
- **Strava activity sync** — import runs via `sync_strava.py`
- **Dashboard** — stat cards, charts, and date-range filters (Last 30 days, Last 90 days, Last 365 days, All time)
- **Recent Runs** — sortable, paginated runs table with weather display
- **Historical weather sync** — backfill run-time weather via `sync_weather.py` (Open-Meteo)
- **Analysis** — weather-based performance charts and **Best Running Conditions** insights
- **Weather Planner** — 7-day forecast matching by temperature and 90-minute time windows (7:00 AM – 10:00 PM)
- **Personalized suggestions** — **Suggested From Your Recent Runs** uses Best Running Conditions to pre-fill the planner

## Tech stack

- Python
- Flask
- SQLite
- Chart.js
- Strava API
- Open-Meteo API (forecast and historical weather)
- HTML / CSS / JavaScript

## Local setup

1. **Create a virtual environment**
  ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate   # macOS/Linux
  ```
2. **Install dependencies**
  ```bash
   pip install -r requirements.txt
  ```
3. **Configure environment variables**
  Copy `.env.example` to `.env` and set:
  - `STRAVA_CLIENT_ID`
  - `STRAVA_CLIENT_SECRET`
  - `STRAVA_REDIRECT_URI`
  - `FLASK_SECRET_KEY`
   OAuth tokens are stored in the local SQLite database after you connect — you do not paste tokens into `.env`.
4. **Run the app**
  ```bash
   python app.py
  ```
   Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/).
5. **Connect Strava and sync runs**
  Visit [http://127.0.0.1:5000/strava/connect](http://127.0.0.1:5000/strava/connect), authorize the app, then:
6. **Sync historical weather** (optional, for Analysis and dashboard weather column)
  ```bash
   python sync_weather.py
  ```
   Requires runs with start times and coordinates from Strava. Re-run `sync_strava.py` first if those fields are missing.

## Strava setup routes

These routes are available for setup and troubleshooting but are **not** in the main navigation:


| Route              | Purpose                                  |
| ------------------ | ---------------------------------------- |
| `/strava/connect`  | Start Strava OAuth                       |
| `/strava/callback` | OAuth redirect handler                   |
| `/strava/status`   | Check `.env` and connection token status |


## Dashboard and Analysis date filters

Both pages support `?range=30d`, `?range=90d`, `?range=365d` (default), and `?range=all`.

## Weather Planner

Set a temperature range and optional 90-minute time window, then find matching forecast hours for the next 7 days. Rain probability is display-only. Use **Use These Conditions** on the recommendation card to apply Best Running Conditions from your last 90 days.

Default location is New Orleans (`WEATHER_LATITUDE`, `WEATHER_LONGITUDE` in `.env`).

## Security

- `.env` and `runtracker.db` are gitignored — do not commit them
- Strava access and refresh tokens are stored locally in SQLite only
- Tokens are never displayed in the browser after OAuth completes

## Optional sample data

For a quick demo without Strava, you can run `python seed_data.py` to populate sample runs. For real use, connect Strava and sync instead.