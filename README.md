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
