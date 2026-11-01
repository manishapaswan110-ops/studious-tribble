# StudyTrack

StudyTrack is a Flask app for organizing student study goals, weekly sessions, notes, and test results. It stores data in a local SQLite database and includes a performance report with a score-history chart.

## Requirements

- Python 3.10 or later
- Windows PowerShell, macOS, or Linux terminal

## Run locally

From the project directory, create and activate a virtual environment:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies and start the app:

```powershell
python -m pip install -r requirements.txt
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
python app.py
```

Open http://127.0.0.1:5000. The SQLite database is created as `studytrack.db` when the app starts. The database and virtual environment are intentionally excluded from Git.

For subsequent runs, set `SECRET_KEY` to a persistent random value before starting the app so browser sessions remain valid across restarts. The generated fallback key is suitable only for local development.

## Features

- Student registration and login
- Study goal tracking
- Weekly study planner
- Study notes
- Test score entry and performance summaries
- Recent score-history chart

## Security note

This project is intended for local learning and demonstration. Before deploying it publicly, configure a persistent secret key and review the app's authentication, CSRF protection, and production server settings.