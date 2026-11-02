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

### Backend API

This project now includes a modular Flask backend under `backend/` for student learning analytics. Start it with:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

The backend exposes JSON API routes under `/api` for authentication, courses, subjects, topics, tests, flashcards, analytics and reports.

### AI study assistant

The existing Study Notes page includes AI summaries, concept explanations, practice quizzes, saved flashcards, and personalized recommendations based on your recorded test results. Add or upload your syllabus from Profile, then choose a saved subject on Study Notes and generate course-aligned notes. Syllabus uploads must be UTF-8 `.txt` or `.md` files, up to 12,000 characters. The dashboard and performance report also link to an AI test flow where students can choose multiple-choice, fill-in-the-blank, or short-answer tests generated from saved notes or pasted material. Test scores are saved to the performance report.

To connect AI, copy `.env.example` to `.env`, add your OpenAI API key locally, then restart the app. Never commit or share `.env`:

```powershell
Copy-Item .env.example .env
# Open .env and replace the placeholder with your key from https://platform.openai.com/api-keys
python app.py
```

The optional model setting defaults to `gpt-4o-mini`. AI actions send the selected note content or your aggregated subject scores to OpenAI. The AI endpoints require a logged-in user; note and flashcard records are scoped to that user.

### Open on another device on your Wi-Fi

Start the app on your computer with `python app.py`, then find its local IPv4 address by running `ipconfig` in PowerShell and checking the active Wi-Fi adapter's `IPv4 Address`. On the other device, open `http://<computer-ip>:5000` (for example, `http://192.168.1.25:5000`). Both devices must be on the same trusted Wi-Fi network. If Windows Firewall prompts you, allow Python on private networks only.

The app listens on the local network for this purpose and runs with Flask's debugger disabled. This is for trusted local-network testing, not public internet hosting.

For subsequent runs, set `SECRET_KEY` to a persistent random value before starting the app so browser sessions remain valid across restarts. The generated fallback key is suitable only for local development.

## Features

- Student registration and login
- Study goal tracking
- Weekly study planner
- Study notes
- Subject upload for personalized study questions
- Test score entry and performance summaries
- Recent score-history chart

## Security note

This project is intended for local learning and demonstration. Before deploying it publicly, configure a persistent secret key and review the app's authentication, CSRF protection, and production server settings.