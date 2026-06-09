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

## Strava sync

After connecting Strava at `/strava/connect`, sync your real run activities into the local database:

```bash
python sync_strava.py
```

The script refreshes your access token, fetches recent Strava activities, and inserts new runs into SQLite. Duplicate activities are skipped automatically.

`runtracker.db` is local, gitignored, and should not be committed. Do not commit `.env` or any OAuth tokens.

To replace sample runs with only Strava data, delete `runtracker.db` and reconnect Strava, or run `python seed_data.py` (this drops and reseeds sample runs only — it does not remove Strava tokens).
