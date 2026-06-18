# RunTracker

**Live site:** [https://runtracker-lirm.onrender.com/](https://runtracker-lirm.onrender.com/)

Note: The live site is hosted on a free service. If it has been inactive, the first load may take up to a minute while the server wakes up.

RunTracker is a personal running analytics app I built to better understand my own training data. I started running in August 2025 and have been recording my runs with an Apple Watch, with Strava storing detailed activity metrics like distance, pace, time, elevation, and run history. This app pulls that running data together with historical weather data for each run, then uses dashboards, charts, and analysis tools to help identify patterns in my performance and make better decisions about future runs.

The current version includes a filterable running dashboard, a full run history table, weather-based performance analysis, and a weather planner that uses recent running patterns and forecast data to suggest upcoming run windows.

## Features

- **Dashboard** — stat cards, charts, and date-range filters (Last 30 days, Last 90 days, Last 365 days, All time)
- **Run Log** — sortable, paginated runs table with weather display
- **Analysis** — performance charts by distance, timing, and temperature, plus **Best Running Conditions** insights
- **Weather Planner** — 7-day New Orleans forecast matching by temperature and 90-minute time windows (7:00 AM – 10:00 PM)
- **Personalized suggestions** — **Suggested From Your Recent Runs** uses Best Running Conditions to pre-fill the planner

## Tech Stack

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- Chart.js
- Strava API
- Open-Meteo API
- Gunicorn
- Render
- Git / GitHub

## Data Sources

RunTracker combines two data streams:

**1. Strava activity data** — Synced locally from the Strava API and stored in SQLite. Includes distance, pace, run date and start time, activity name, elevation when available, and other synced run fields.

**2. Open-Meteo data** — Historical weather matched to past runs by date, time, and coordinates for analysis and the Run Log, plus 7-day New Orleans forecast data used by the Weather Planner to suggest upcoming running windows.

## How the Data Is Processed

1. **Strava sync** — Runs are imported locally through the Strava API (`sync_strava.py`).
2. **SQLite storage** — Run records, pace values, start times, and synced metadata are stored in `runtracker.db`.
3. **Historical weather sync** — Past runs with coordinates and start times receive matched weather (`sync_weather.py`).
4. **Public database export** — A sanitized copy is generated for deployment (`create_public_db.py`), stripping tokens and sensitive fields.
5. **Dashboard and Analysis** — Flask routes query SQLite, filter by selected date range, and aggregate data through Python helper functions for charts and stat cards.
6. **Weather Planner** — Uses live forecast data from Open-Meteo plus Best Running Conditions from recent weather-backed runs to suggest windows.

## Chart Methodology

All pace calculations use numeric `pace_seconds` (seconds per mile). Displayed pace is formatted as minutes per mile. **Lower pace means faster.**

Dashboard and Analysis pages support date filters: `?range=30d`, `?range=90d`, `?range=365d` (default), and `?range=all`.

### Dashboard

| Chart | Calculation | Chart type |
|-------|-------------|------------|
| **Weekly Mileage** | Sum of `distance_miles` per week; week starts Monday | Bar |
| **Monthly Mileage** | Sum of `distance_miles` per calendar month | Bar |
| **Longest Run by Month** | Maximum single-run `distance_miles` per calendar month | Bar |
| **Pace Trend** | Mean `pace_seconds` per week (Monday week start) | Line |

Stat cards on the Dashboard use the same filtered run list: total miles, run count, longest run, and overall average pace.

### Analysis

| Chart | Calculation | Chart type |
|-------|-------------|------------|
| **Distance vs Pace** | One point per run: distance vs `pace_seconds` | Scatter |
| **Average Pace by Distance Bucket** | Runs grouped into mutually exclusive distance buckets (0–2, 2–3, 3–4, 4–5, 5–6, 6+ mi); mean `pace_seconds` per bucket | Bar |
| **Distance Distribution** | Count of runs per distance bucket | Bar |
| **Runs by Day of Week** | Count of runs per weekday | Bar |
| **Runs by Time of Day** | Count of runs per 90-minute start-time window (7:00 AM – 10:00 PM) | Bar |
| **Average Pace by Time of Day** | Mean `pace_seconds` per same time-of-day bucket | Bar |
| **Pace vs Temperature** | One point per weather-backed run: temperature vs `pace_seconds` | Scatter |
| **Average Pace by Temperature** | Weather-backed runs grouped into 10°F temperature buckets; mean `pace_seconds` per bucket | Bar |

## Best Running Conditions

An aggregate insight panel derived from recent weather-backed runs:

1. Filter to runs at least **2 miles** long with valid pace, temperature, and qualifying start time (7:00 AM – 10:00 PM buckets).
2. Group runs by **time-of-day bucket** and **temperature bucket**.
3. Keep only groups with at least **5 runs**.
4. Select the group with the **fastest average pace** (`pace_seconds`).
5. Display summary stats: best time window, temperature range, average pace, run count, average distance, and average temperature.

This identifies the strongest aggregate pattern in the selected date range. It is an exploratory insight, not a guarantee of future performance.

## Weather Planner

Set a temperature range and optional 90-minute time window, then find matching forecast hours for the next 7 days. Use **Use These Conditions** on the recommendation card to apply Best Running Conditions from your last 90 days.

## Screenshots

### Dashboard

The Dashboard summarizes running volume, pace, long runs, weekly mileage, monthly mileage, and recent runs with filtering, sorting, and pagination.

![Dashboard screenshot](docs/screenshots/dashboard.png)

### Analysis

The Analysis page explores performance patterns by distance, weekday, time of day, and temperature, plus Best Running Conditions when enough weather-backed data exists.

![Analysis screenshot](docs/screenshots/analysis.png)

### Weather Planner

The Weather Planner uses New Orleans forecast data and recent running patterns to help identify upcoming run windows that match selected temperature and time preferences.

![Weather Planner screenshot](docs/screenshots/weather-planner.png)

## Local Development Setup

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

   Copy `.env.example` to `.env` and set at least `FLASK_SECRET_KEY`.

   For local Strava sync development, also set:

   - `STRAVA_CLIENT_ID`
   - `STRAVA_CLIENT_SECRET`
   - `STRAVA_REDIRECT_URI`
   - `ENABLE_STRAVA_ROUTES=true`

   OAuth tokens are stored in the local SQLite database after you connect. Do not paste tokens into `.env`.

4. **Run the app**

   ```bash
   python app.py
   ```

   Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/).

5. **Connect Strava and sync runs** (local development only)

   With `ENABLE_STRAVA_ROUTES=true`, visit [http://127.0.0.1:5000/strava/connect](http://127.0.0.1:5000/strava/connect), authorize the app, then run the sync scripts described in [Updating Run Data](#updating-run-data).

## Updating Run Data

Because the live version uses `public_runtracker.db`, run data updates require regenerating the sanitized public database locally and pushing it to GitHub.

1. **Sync new Strava activities**

   ```powershell
   python sync_strava.py
   ```

2. **Sync historical weather for newly imported runs**

   ```powershell
   python sync_weather.py
   ```

3. **Rebuild the sanitized public database**

   ```powershell
   python create_public_db.py
   ```

4. **Verify the public database is safe**

   ```powershell
   python verify_public_db.py
   ```

5. **Test locally with the public database**

   ```powershell
   $env:DATABASE_PATH="public_runtracker.db"
   $env:ENABLE_STRAVA_ROUTES="false"
   python app.py
   ```

6. **Commit and push the updated public database**

   ```powershell
   git status
   git add public_runtracker.db README.md
   git commit -m "Update public running data"
   git push
   ```

To update the data cutoff date shown in documentation, use the latest run date printed by `create_public_db.py`.

## Deployment Notes

- The app is deployed on [Render](https://render.com/).
- Start command: `gunicorn app:app`
- The live service should use:
  - `DATABASE_PATH=public_runtracker.db`
  - `ENABLE_STRAVA_ROUTES=false`
- Strava OAuth routes are disabled in the live version.
- The live version does not need Strava secrets because it uses the sanitized public database.

A `Procfile` is included for Render and similar platforms.

## Security Notes

- Do **not** commit `.env`
- Do **not** commit `runtracker.db`
- Do **not** commit private database backups
- Only `public_runtracker.db` should be committed as a database file
- Run `python verify_public_db.py` before committing an updated public database
- `public_runtracker.db` should not contain Strava tokens, OAuth tables, access tokens, refresh tokens, client secrets, or exact coordinates

## Future Improvements / To Do

- Add automatic daily Strava sync
- Add automatic weather sync after new runs are imported
- Add user accounts
- Allow users to connect their own Strava accounts
- Allow configurable weather location instead of hardcoded New Orleans
- Add admin-only sync controls
- Move to a production database if the app becomes multi-user
- Add tests for analysis and database helper functions
- Add more screenshots or demo GIFs if useful

## Optional Sample Data

For a quick demo without Strava, you can run `python seed_data.py` to populate sample runs. For real use, connect Strava and sync instead.
