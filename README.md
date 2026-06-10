# RunTracker

RunTracker is a personal running analytics app that combines Strava activity data with historical and forecast weather data. The current version includes a filterable dashboard, performance analysis, and a New Orleans weather planner.

## Features

- **Dashboard** — stat cards, charts, and date-range filters (Last 30 days, Last 90 days, Last 365 days, All time)
- **Recent Runs** — sortable, paginated runs table with weather display
- **Analysis** — weather-based performance charts and **Best Running Conditions** insights
- **Weather Planner** — 7-day New Orleans forecast matching by temperature and 90-minute time windows (7:00 AM – 10:00 PM)
- **Personalized suggestions** — **Suggested From Your Recent Runs** uses Best Running Conditions to pre-fill the planner

## Tech stack

- Python
- Flask
- SQLite
- Chart.js
- Strava API (local development sync only)
- Open-Meteo API (forecast and historical weather)
- HTML / CSS / JavaScript

## Local development setup

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

   OAuth tokens are stored in the local SQLite database after you connect — you do not paste tokens into `.env`.

4. **Run the app**

   ```bash
   python app.py
   ```

   Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/).

5. **Connect Strava and sync runs** (local development only)

   With `ENABLE_STRAVA_ROUTES=true`, visit [http://127.0.0.1:5000/strava/connect](http://127.0.0.1:5000/strava/connect), authorize the app, then:

   ```bash
   python sync_strava.py
   python sync_weather.py
   ```

## Current version notes

The live/public version of RunTracker uses a **sanitized snapshot** of running and weather data stored in `public_runtracker.db`.

- Running data in the current version is included through: **2026-06-09** (update this date after each public export).
- The app does **not** automatically sync new Strava activities in the live version.
- New run data is added manually by running:

  ```bash
  python sync_strava.py
  python sync_weather.py
  python create_public_db.py
  ```

- The Weather Planner uses **New Orleans** forecast data (`America/Chicago` timezone).
- Exact run coordinates are **not** included in the public database.
- Strava tokens, client secrets, and OAuth tables are **not** included in the public database.
- Public visitors **cannot** connect their own Strava accounts in the current version (`ENABLE_STRAVA_ROUTES=false` by default).

### Create the public database

```bash
python create_public_db.py
```

The script prints the latest run date copied — paste that date into the README cutoff line above.

### Run locally with the public database

PowerShell:

```powershell
$env:DATABASE_PATH="public_runtracker.db"
$env:ENABLE_STRAVA_ROUTES="false"
python app.py
```

macOS/Linux:

```bash
export DATABASE_PATH=public_runtracker.db
export ENABLE_STRAVA_ROUTES=false
python app.py
```

Then open:

- [http://127.0.0.1:5000/](http://127.0.0.1:5000/)
- [http://127.0.0.1:5000/analysis](http://127.0.0.1:5000/analysis)
- [http://127.0.0.1:5000/weather](http://127.0.0.1:5000/weather)

### Production start command

```bash
gunicorn app:app
```

A `Procfile` is included for platforms such as Render.

## Dashboard and Analysis date filters

Both pages support `?range=30d`, `?range=90d`, `?range=365d` (default), and `?range=all`.

## Weather Planner

Set a temperature range and optional 90-minute time window, then find matching forecast hours for the next 7 days. Rain probability is display-only. Use **Use These Conditions** on the recommendation card to apply Best Running Conditions from your last 90 days.

## Security

**Do not commit:**

- `.env`
- `runtracker.db`
- any other local/private database files

**Safe to commit:**

- `public_runtracker.db` (sanitized read-only snapshot)

Strava access and refresh tokens stay in local development databases only and are never copied into the public database.

## Future improvements / To Do

- Add automatic daily Strava sync
- Add automatic weather sync after new runs are imported
- Add user accounts
- Allow users to connect their own Strava accounts
- Allow configurable weather location
- Replace SQLite with a production database if needed
- Add private/admin-only sync controls
- Add tests for analysis helpers
- Add deployment-specific documentation

## Optional sample data

For a quick demo without Strava, you can run `python seed_data.py` to populate sample runs. For real use, connect Strava and sync instead.
