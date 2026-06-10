# RunTracker

Personal Flask app for running stats, trends, and training insights.

## Local setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate   # macOS/Linux
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and add your Strava app credentials (`STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REDIRECT_URI`). OAuth access and refresh tokens are stored locally in SQLite after you connect via `/strava/connect` — you do not need to paste tokens into `.env`.

   `runtracker.db` is gitignored and should not be committed.

4. Seed the database:

   ```bash
   python seed_data.py
   ```

5. Run the app:

   ```bash
   python app.py
   ```

   Open `http://127.0.0.1:5000/` in your browser.

## Dashboard and analysis

The dashboard supports date-range filters via query parameters:

- `/?range=30d` — last 30 days
- `/?range=90d` — last 90 days
- `/?range=365d` — last 365 days (default)
- `/?range=all` — all time

Stat cards, charts, and the Recent Runs table all use the same selected range. Legacy `/?range=ytd` URLs redirect to the same data as `365d`.

The **Analysis** page (`/analysis`) shows weekday and time-of-day patterns, average pace by day, and a distance-vs-pace scatter chart. A placeholder section is reserved for future weather-based insights.

Strava-synced runs store local start time (`start_time_display`, e.g. `7:30 PM`) plus weekday and hour fields used in the dashboard and analysis views.

## Strava sync

After connecting Strava at `/strava/connect`, sync your real run activities into the local database:

```bash
python sync_strava.py
```

The script refreshes your access token, fetches recent Strava activities, and inserts new runs into SQLite. Duplicate activities are skipped, but existing runs missing start-time fields are backfilled on re-sync.

`runtracker.db` is local, gitignored, and should not be committed. Do not commit `.env` or any OAuth tokens.

To replace sample runs with only Strava data, delete `runtracker.db` and reconnect Strava, or run `python seed_data.py` (this drops and reseeds sample runs only — it does not remove Strava tokens).
