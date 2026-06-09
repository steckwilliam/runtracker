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

3. Optional: copy `.env.example` to `.env` when you need local config overrides (API keys, secret key, etc.). Defaults work for local development without a `.env` file.

4. Seed the database:

   ```bash
   python seed_data.py
   ```

5. Run the app:

   ```bash
   python app.py
   ```

   Open `http://127.0.0.1:5000/` in your browser.
