
import os
import re
import secrets
import sqlite3
import json
from functools import wraps
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv(Path(__file__).with_name(".env"))

from ai_service import (
    AIServiceError,
    explain_concept,
    generate_flashcards,
    generate_quiz,
    generate_recommendations,
    generate_syllabus_notes,
    generate_test_questions,
    grade_short_answers,
    summarize_notes,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
MAX_AI_SOURCE_LENGTH = 12000
MAX_SYLLABUS_LENGTH = 12000


def get_db_connection():
    conn = sqlite3.connect("studytrack.db")
    conn.row_factory = sqlite3.Row
    return conn


# Create database
def create_database():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            education TEXT NOT NULL,
            course TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS student_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES students(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS study_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            target_date TEXT,
            completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES students(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            day TEXT NOT NULL,
            time TEXT,
            duration INTEGER NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES students(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS study_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES students(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            test_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES students(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS study_flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            note_id INTEGER,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES students(id),
            FOREIGN KEY (note_id) REFERENCES study_notes(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_test_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            question_type TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            answers_json TEXT,
            score INTEGER,
            total INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES students(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS student_syllabi (
            user_id INTEGER PRIMARY KEY,
            syllabus_text TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES students(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_test_attempts_user_id ON ai_test_attempts (user_id)"
    )
    conn.commit()
    conn.close()


# Ensure the SQLite database exists even when the app is imported by Flask or WSGI.
create_database()


def ai_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required."}), 401
        if request.method == "POST":
            supplied_token = request.headers.get("X-CSRF-Token", "")
            expected_token = session.get("_ai_csrf_token", "")
            if not expected_token or not secrets.compare_digest(supplied_token, expected_token):
                return jsonify({"error": "Invalid request token. Reload the page and try again."}), 403
        return view(*args, **kwargs)

    return wrapped


def _ai_source(payload):
    if not isinstance(payload, dict):
        return None, None, None, (jsonify({"error": "A JSON object is required."}), 400)

    note_id = payload.get("note_id")
    if note_id is not None:
        if isinstance(note_id, bool):
            return None, None, None, (jsonify({"error": "note_id must be an integer."}), 400)
        if isinstance(note_id, str):
            if not note_id.isdecimal():
                return None, None, None, (jsonify({"error": "note_id must be an integer."}), 400)
            note_id = int(note_id)
        elif not isinstance(note_id, int):
            return None, None, None, (jsonify({"error": "note_id must be an integer."}), 400)

        conn = get_db_connection()
        note = conn.execute(
            "SELECT id, title, content FROM study_notes WHERE id = ? AND user_id = ?",
            (note_id, session["user_id"]),
        ).fetchone()
        conn.close()
        if note is None:
            return None, None, None, (jsonify({"error": "Note not found."}), 404)
        title, content = note["title"], note["content"]
    else:
        topic = payload.get("topic")
        requested_title = payload.get("title") or topic or "Study material"
        if not isinstance(requested_title, str):
            return None, None, None, (jsonify({"error": "title and topic must be text."}), 400)
        title = requested_title.strip() or "Study material"
        if len(title) > 200:
            return None, None, None, (jsonify({"error": "title and topic cannot exceed 200 characters."}), 400)
        content = payload.get("text") or (topic if isinstance(topic, str) else "")
        note_id = None

    if not isinstance(content, str) or not content.strip():
        return None, None, None, (jsonify({"error": "Provide a saved note or non-empty text."}), 400)
    content = content.strip()
    if len(content) > MAX_AI_SOURCE_LENGTH:
        return None, None, None, (jsonify({"error": f"Study material cannot exceed {MAX_AI_SOURCE_LENGTH} characters."}), 413)
    return title, content, note_id, None


def _ai_count(payload, field, default, maximum):
    value = payload.get(field, default)
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        if not value.isdecimal():
            return None
        value = int(value)
    elif not isinstance(value, int):
        return None
    return value if 1 <= value <= maximum else None


def _public_test_questions(questions, question_type):
    public_questions = []
    for question in questions:
        if question_type == "mcq":
            public_questions.append({
                "question": question["question"],
                "options": question["options"],
            })
        elif question_type == "fill_blank":
            public_questions.append({"prompt": question["prompt"]})
        else:
            public_questions.append({"question": question["question"]})
    return public_questions


def _normalize_answer(answer):
    return re.sub(r"[\W_]+", "", answer.casefold(), flags=re.UNICODE)


# Welcome page
@app.route("/")
def home():
    return render_template("welcome.html", user_name=session.get("user_name"))


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    user = conn.execute(
        "SELECT name, email, education, course FROM students WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    subjects = conn.execute(
        "SELECT subject_name FROM student_subjects WHERE user_id = ? ORDER BY subject_name",
        (session["user_id"],),
    ).fetchall()
    goals = conn.execute(
        "SELECT id, title, target_date, completed FROM study_goals WHERE user_id = ? ORDER BY completed ASC, target_date ASC LIMIT 3",
        (session["user_id"],),
    ).fetchall()
    syllabus = conn.execute(
        "SELECT 1 FROM student_syllabi WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()
    score_focus = conn.execute(
        """
        SELECT subject, ROUND(AVG(100.0 * score / total), 1) AS average_percentage
        FROM test_results
        WHERE user_id = ? AND total > 0
        GROUP BY subject
        ORDER BY average_percentage ASC, subject ASC
        LIMIT 1
        """,
        (session["user_id"],),
    ).fetchone()
    conn.close()

    progress = {
        "weekly_hours": 12,
        "goal_hours": 15,
        "completed_lessons": 7,
        "total_lessons": 10,
        "streak_days": 5,
        "next_goal": "Finish Python revision module"
    }
    progress["hours_percent"] = min(100, int((progress["weekly_hours"] / progress["goal_hours"]) * 100))
    progress["lessons_percent"] = min(100, int((progress["completed_lessons"] / progress["total_lessons"]) * 100))

    subject_list = [row["subject_name"] for row in subjects]
    focus_subject = score_focus["subject"] if score_focus else (
        subject_list[0] if subject_list else None
    )
    return render_template(
        "dashboard.html",
        user=user,
        progress=progress,
        goals=goals,
        subjects=subject_list,
        has_syllabus=syllabus is not None,
        focus_subject=focus_subject,
        focus_percentage=score_focus["average_percentage"] if score_focus else None,
    )


# Login page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM students WHERE email = ?",
            (email,),
        ).fetchone()
        conn.close()

        if user is None:
            return render_template("login.html", error="No account found with that email.")

        if not check_password_hash(user["password"], password):
            return render_template("login.html", error="Incorrect password.")

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session.pop("_ai_csrf_token", None)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("_ai_csrf_token", None)
    return redirect(url_for("home"))


@app.route("/goals", methods=["GET", "POST"])
def goals():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["goal_title"].strip()
        target_date = request.form.get("target_date")

        if title:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO study_goals (user_id, title, target_date, completed) VALUES (?, ?, ?, 0)",
                (session["user_id"], title, target_date),
            )
            conn.commit()
            conn.close()

        return redirect(url_for("goals"))

    conn = get_db_connection()
    goals_list = conn.execute(
        "SELECT id, title, target_date, completed FROM study_goals WHERE user_id = ? ORDER BY completed ASC, target_date ASC",
        (session["user_id"],),
    ).fetchall()
    conn.close()

    completed_count = sum(goal["completed"] for goal in goals_list)
    return render_template(
        "goals.html",
        goals=goals_list,
        active_count=len(goals_list) - completed_count,
        completed_count=completed_count,
        today=date.today().isoformat(),
    )


@app.route("/planner", methods=["GET", "POST"])
def planner():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["session_title"].strip()
        day = request.form["day"]
        time = request.form.get("time")
        duration = request.form.get("duration", 0)
        notes = request.form.get("notes", "").strip()

        if title and day:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO study_sessions (user_id, title, day, time, duration, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (session["user_id"], title, day, time, int(duration or 0), notes),
            )
            conn.commit()
            conn.close()

        return redirect(url_for("planner"))

    conn = get_db_connection()
    sessions = conn.execute(
        "SELECT id, title, day, time, duration, notes FROM study_sessions WHERE user_id = ? ORDER BY day, time",
        (session["user_id"],),
    ).fetchall()
    conn.close()

    return render_template("planner.html", sessions=sessions)


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, name, email, education, course FROM students WHERE id = ?",
        (session["user_id"],),
    ).fetchone()

    if request.method == "POST":
        name = request.form["name"].strip()
        education = request.form["education"]
        course = request.form["course"].strip()
        subject_input = request.form.get("subjects", "")
        uploaded_file = request.files.get("subjects_file")
        syllabus_text = request.form.get("syllabus_text", "").strip()
        syllabus_file = request.files.get("syllabus_file")

        if syllabus_file and syllabus_file.filename:
            if not syllabus_file.filename.lower().endswith((".txt", ".md")):
                conn.close()
                return render_template(
                    "profile.html",
                    user=user,
                    subjects_text=subject_input,
                    syllabus_text=syllabus_text,
                    error="Upload a syllabus as a .txt or .md file.",
                ), 400
            uploaded_syllabus = syllabus_file.read(MAX_SYLLABUS_LENGTH + 1)
            if len(uploaded_syllabus) > MAX_SYLLABUS_LENGTH:
                conn.close()
                return render_template(
                    "profile.html",
                    user=user,
                    subjects_text=subject_input,
                    syllabus_text=syllabus_text,
                    error=f"Syllabus files must be no larger than {MAX_SYLLABUS_LENGTH} bytes.",
                ), 413
            try:
                syllabus_text = uploaded_syllabus.decode("utf-8").strip()
            except UnicodeDecodeError:
                conn.close()
                return render_template(
                    "profile.html",
                    user=user,
                    subjects_text=subject_input,
                    syllabus_text="",
                    error="The syllabus file must be valid UTF-8 text.",
                ), 400

        if len(syllabus_text) > MAX_SYLLABUS_LENGTH:
            conn.close()
            return render_template(
                "profile.html",
                user=user,
                subjects_text=subject_input,
                syllabus_text=syllabus_text,
                error=f"Syllabus text cannot exceed {MAX_SYLLABUS_LENGTH} characters.",
            ), 413

        if uploaded_file and uploaded_file.filename:
            try:
                uploaded_text = uploaded_file.read().decode("utf-8", errors="replace")
                if uploaded_text:
                    subject_input = f"{subject_input}\n{uploaded_text}" if subject_input else uploaded_text
            except Exception:
                pass

        if name:
            conn.execute(
                "UPDATE students SET name = ?, education = ?, course = ? WHERE id = ?",
                (name, education, course, session["user_id"]),
            )
            conn.commit()
            session["user_name"] = name
            user = conn.execute(
                "SELECT id, name, email, education, course FROM students WHERE id = ?",
                (session["user_id"],),
            ).fetchone()

        subject_names = []
        seen = set()
        for value in re.split(r"[\n,;]+", subject_input):
            subject_name = re.sub(r"\s+", " ", value).strip()
            if not subject_name:
                continue
            normalized = subject_name.lower()
            if normalized not in seen:
                seen.add(normalized)
                subject_names.append(subject_name)

        conn.execute("DELETE FROM student_subjects WHERE user_id = ?", (session["user_id"],))
        for subject_name in subject_names:
            conn.execute(
                "INSERT INTO student_subjects (user_id, subject_name) VALUES (?, ?)",
                (session["user_id"], subject_name),
            )
        if syllabus_text:
            conn.execute(
                """
                INSERT INTO student_syllabi (user_id, syllabus_text, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    syllabus_text = excluded.syllabus_text,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (session["user_id"], syllabus_text),
            )
        else:
            conn.execute(
                "DELETE FROM student_syllabi WHERE user_id = ?",
                (session["user_id"],),
            )
        conn.commit()

        conn.close()
        return redirect(url_for("profile"))

    subject_rows = conn.execute(
        "SELECT subject_name FROM student_subjects WHERE user_id = ? ORDER BY subject_name",
        (session["user_id"],),
    ).fetchall()
    syllabus_row = conn.execute(
        "SELECT syllabus_text FROM student_syllabi WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()
    conn.close()
    subjects_text = "\n".join(row["subject_name"] for row in subject_rows)
    syllabus_text = syllabus_row["syllabus_text"] if syllabus_row else ""
    return render_template(
        "profile.html",
        user=user,
        subjects_text=subjects_text,
        syllabus_text=syllabus_text,
    )


@app.route("/notes", methods=["GET", "POST"])
def notes():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["note_title"].strip()
        content = request.form["content"].strip()

        if title and content:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO study_notes (user_id, title, content) VALUES (?, ?, ?)",
                (session["user_id"], title, content),
            )
            conn.commit()
            conn.close()

        return redirect(url_for("notes"))

    conn = get_db_connection()
    note_list = conn.execute(
        "SELECT id, title, content, created_at FROM study_notes WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    subjects = conn.execute(
        "SELECT subject_name FROM student_subjects WHERE user_id = ? ORDER BY subject_name",
        (session["user_id"],),
    ).fetchall()
    syllabus = conn.execute(
        "SELECT 1 FROM student_syllabi WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()
    conn.close()

    if "_ai_csrf_token" not in session:
        session["_ai_csrf_token"] = secrets.token_urlsafe(32)
    return render_template(
        "notes.html",
        notes=note_list,
        subjects=subjects,
        has_syllabus=syllabus is not None,
        ai_configured=bool(os.getenv("OPENAI_API_KEY")),
        ai_csrf_token=session["_ai_csrf_token"],
    )


@app.route("/ai/syllabus-notes", methods=["POST"])
@ai_login_required
def ai_syllabus_notes():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    subject = payload.get("subject")
    if not isinstance(subject, str) or not subject.strip() or len(subject.strip()) > 120:
        return jsonify({"error": "Choose a subject from your syllabus."}), 400

    conn = get_db_connection()
    user = conn.execute(
        "SELECT course, education FROM students WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    syllabus = conn.execute(
        "SELECT syllabus_text FROM student_syllabi WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()
    subjects = conn.execute(
        "SELECT subject_name FROM student_subjects WHERE user_id = ?",
        (session["user_id"],),
    ).fetchall()
    if syllabus is None:
        conn.close()
        return jsonify({"error": "Add your syllabus in Profile before generating notes."}), 400
    if subjects and subject.strip().casefold() not in {
        row["subject_name"].casefold() for row in subjects
    }:
        conn.close()
        return jsonify({"error": "Choose one of your saved study subjects."}), 400

    course = user["course"]
    education = user["education"]
    syllabus_text = syllabus["syllabus_text"]
    conn.close()

    try:
        notes = generate_syllabus_notes(
            course,
            education,
            subject.strip(),
            syllabus_text,
        )
    except AIServiceError as error:
        app.logger.warning("Syllabus note generation failed: %s", error)
        return jsonify({"error": str(error)}), 503

    note_title = f"{subject.strip()} - {notes['title']}"
    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO study_notes (user_id, title, content) VALUES (?, ?, ?)",
        (session["user_id"], note_title, notes["notes"]),
    )
    note_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({
        "note": {
            "id": note_id,
            "title": note_title,
            "content": notes["notes"],
        },
        "message": "Syllabus-based notes generated and saved.",
    }), 201


@app.route("/start-test")
def start_test_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    notes_list = conn.execute(
        "SELECT id, title FROM study_notes WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    subjects = conn.execute(
        "SELECT subject_name FROM student_subjects WHERE user_id = ? ORDER BY subject_name",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    requested_subject = request.args.get("subject", "").strip()
    allowed_subjects = {row["subject_name"] for row in subjects}
    selected_subject = requested_subject if requested_subject in allowed_subjects else ""
    if "_ai_csrf_token" not in session:
        session["_ai_csrf_token"] = secrets.token_urlsafe(32)
    return render_template(
        "start_test.html",
        notes=notes_list,
        subjects=subjects,
        selected_subject=selected_subject,
        ai_configured=bool(os.getenv("OPENAI_API_KEY")),
        ai_csrf_token=session["_ai_csrf_token"],
    )


@app.route("/ai/start-test", methods=["POST"])
@ai_login_required
def ai_start_test():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    question_type = payload.get("question_type")
    if not isinstance(question_type, str) or question_type not in {"mcq", "fill_blank", "short_answer"}:
        return jsonify({"error": "Choose MCQ, fill-in-the-blank, or short-answer questions."}), 400
    subject = payload.get("subject")
    if not isinstance(subject, str) or not subject.strip() or len(subject.strip()) > 120:
        return jsonify({"error": "Enter a subject between 1 and 120 characters."}), 400

    title, content, _, error = _ai_source(payload)
    if error:
        return error

    count = _ai_count(payload, "count", 5, 10)
    if count is None:
        return jsonify({"error": "Question count must be between 1 and 10."}), 400

    try:
        questions = generate_test_questions(title, content, question_type, count)
    except AIServiceError as error:
        app.logger.warning("AI test generation failed: %s", error)
        return jsonify({"error": str(error)}), 503

    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO ai_test_attempts (user_id, subject, question_type, questions_json, total)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session["user_id"], subject.strip(), question_type, json.dumps(questions), len(questions)),
    )
    attempt_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({
        "test_id": attempt_id,
        "subject": subject.strip(),
        "question_type": question_type,
        "questions": _public_test_questions(questions, question_type),
    }), 201


@app.route("/ai/submit-test", methods=["POST"])
@ai_login_required
def ai_submit_test():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    test_id = payload.get("test_id")
    if isinstance(test_id, bool):
        return jsonify({"error": "test_id must be an integer."}), 400
    if isinstance(test_id, str):
        if not test_id.isdecimal():
            return jsonify({"error": "test_id must be an integer."}), 400
        test_id = int(test_id)
    elif not isinstance(test_id, int):
        return jsonify({"error": "test_id must be an integer."}), 400

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        return jsonify({"error": "answers must be an object keyed by question number."}), 400

    conn = get_db_connection()
    attempt = conn.execute(
        "SELECT * FROM ai_test_attempts WHERE id = ? AND user_id = ?",
        (test_id, session["user_id"]),
    ).fetchone()
    if attempt is None:
        conn.close()
        return jsonify({"error": "Test not found."}), 404
    if attempt["completed_at"] is not None:
        conn.close()
        return jsonify({"error": "This test has already been submitted."}), 409

    questions = json.loads(attempt["questions_json"])
    if any(not str(index).isdecimal() or int(index) >= len(questions) for index in answers):
        conn.close()
        return jsonify({"error": "An answer refers to an invalid question."}), 400
    if any(not isinstance(answer, str) or len(answer) > 2000 for answer in answers.values()):
        conn.close()
        return jsonify({"error": "Each answer must be text no longer than 2,000 characters."}), 400

    question_type = attempt["question_type"]
    if question_type == "mcq" and any(
        answer.strip() and answer.strip().upper() not in {"A", "B", "C", "D"}
        for answer in answers.values()
    ):
        conn.close()
        return jsonify({"error": "Select one of the listed choices for each MCQ."}), 400

    results = []
    score = 0

    if question_type == "short_answer":
        pending_indexes = [
            index for index in range(len(questions))
            if answers.get(str(index), "").strip()
        ]
        grading_inputs = [
            {
                "question": questions[index]["question"],
                "expected_answer": questions[index]["expected_answer"],
                "rubric": questions[index]["rubric"],
                "student_answer": answers[str(index)].strip(),
            }
            for index in pending_indexes
        ]
        grades = []
        if grading_inputs:
            try:
                grades = grade_short_answers(grading_inputs)
            except AIServiceError as error:
                conn.close()
                app.logger.warning("AI short-answer grading failed: %s", error)
                return jsonify({"error": str(error)}), 503
        grade_by_index = dict(zip(pending_indexes, grades))
        for index, question in enumerate(questions):
            grade = grade_by_index.get(index)
            correct = bool(grade and grade["correct"])
            if correct:
                score += 1
            results.append({
                "question": question["question"],
                "answer": answers.get(str(index), "").strip(),
                "expected_answer": question["expected_answer"],
                "correct": correct,
                "feedback": grade["feedback"] if grade else "No answer provided.",
            })
    else:
        for index, question in enumerate(questions):
            answer = answers.get(str(index), "").strip()
            if question_type == "mcq":
                correct = answer.upper() == question["correct_option"]
                expected_answer = question["correct_option"]
                feedback = question["explanation"]
            else:
                expected_answer = question["accepted_answers"][0]
                accepted = {_normalize_answer(value) for value in question["accepted_answers"]}
                correct = bool(answer) and _normalize_answer(answer) in accepted
                feedback = "Correct." if correct else f"Accepted answer: {expected_answer}"
            if correct:
                score += 1
            result = {
                "question": question.get("question", question.get("prompt")),
                "answer": answer,
                "correct": correct,
                "expected_answer": expected_answer,
                "feedback": feedback,
            }
            results.append(result)

    total = len(questions)
    percentage = round(score / total * 100, 1) if total else 0
    update = conn.execute(
        """
        UPDATE ai_test_attempts
        SET answers_json = ?, score = ?, completed_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ? AND completed_at IS NULL
        """,
        (json.dumps(answers), score, test_id, session["user_id"]),
    )
    if update.rowcount != 1:
        conn.rollback()
        conn.close()
        return jsonify({"error": "This test has already been submitted."}), 409
    conn.execute(
        """
        INSERT INTO test_results (user_id, subject, score, total, test_type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session["user_id"],
            attempt["subject"],
            score,
            total,
            f"AI {question_type.replace('_', ' ').title()}",
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({
        "score": score,
        "total": total,
        "percentage": percentage,
        "results": results,
    })


@app.route("/ai/summarize", methods=["POST"])
@ai_login_required
def ai_summarize():
    payload = request.get_json(silent=True)
    title, content, _, error = _ai_source(payload)
    if error:
        return error
    try:
        return jsonify({"summary": summarize_notes(title, content)})
    except AIServiceError as error:
        app.logger.warning("AI summary request failed: %s", error)
        return jsonify({"error": str(error)}), 503


@app.route("/ai/explain", methods=["POST"])
@ai_login_required
def ai_explain():
    payload = request.get_json(silent=True)
    title, content, _, error = _ai_source(payload)
    if error:
        return error
    concept = payload.get("concept")
    if not isinstance(concept, str) or not concept.strip():
        return jsonify({"error": "A concept to explain is required."}), 400
    if len(concept) > 200:
        return jsonify({"error": "The concept cannot exceed 200 characters."}), 400
    try:
        return jsonify({"explanation": explain_concept(title, content, concept.strip())})
    except AIServiceError as error:
        app.logger.warning("AI explanation request failed: %s", error)
        return jsonify({"error": str(error)}), 503


@app.route("/ai/quiz", methods=["POST"])
@ai_login_required
def ai_quiz():
    payload = request.get_json(silent=True)
    title, content, _, error = _ai_source(payload)
    if error:
        return error
    count = _ai_count(payload, "count", 5, 10)
    if count is None:
        return jsonify({"error": "count must be between 1 and 10."}), 400
    try:
        return jsonify({"questions": generate_quiz(title, content, count)})
    except AIServiceError as error:
        app.logger.warning("AI quiz request failed: %s", error)
        return jsonify({"error": str(error)}), 503


@app.route("/ai/flashcards", methods=["POST"])
@ai_login_required
def ai_flashcards():
    payload = request.get_json(silent=True)
    title, content, note_id, error = _ai_source(payload)
    if error:
        return error
    count = _ai_count(payload, "count", 5, 20)
    if count is None:
        return jsonify({"error": "count must be between 1 and 20."}), 400
    try:
        cards = generate_flashcards(title, content, count)
    except AIServiceError as error:
        app.logger.warning("AI flashcard request failed: %s", error)
        return jsonify({"error": str(error)}), 503

    conn = get_db_connection()
    conn.executemany(
        "INSERT INTO study_flashcards (user_id, note_id, question, answer) VALUES (?, ?, ?, ?)",
        [
            (session["user_id"], note_id, card["question"], card["answer"])
            for card in cards
        ],
    )
    conn.commit()
    conn.close()
    return jsonify({"flashcards": cards, "saved": True}), 201


@app.route("/ai/flashcards", methods=["GET"])
@ai_login_required
def list_ai_flashcards():
    conn = get_db_connection()
    cards = conn.execute(
        """
        SELECT id, note_id, question, answer, created_at
        FROM study_flashcards
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return jsonify({"flashcards": [dict(card) for card in cards]})


@app.route("/ai/recommendations", methods=["POST"])
@ai_login_required
def ai_recommendations():
    conn = get_db_connection()
    results = conn.execute(
        """
        SELECT subject, COUNT(*) AS tests,
               ROUND(AVG(100.0 * score / total), 1) AS average_percentage
        FROM test_results
        WHERE user_id = ? AND total > 0
        GROUP BY subject
        ORDER BY average_percentage ASC
        """,
        (session["user_id"],),
    ).fetchall()
    conn.close()
    performance = {
        "subjects": [dict(result) for result in results],
        "assessment_count": sum(result["tests"] for result in results),
    }
    try:
        recommendations = generate_recommendations(performance)
    except AIServiceError as error:
        app.logger.warning("AI recommendation request failed: %s", error)
        return jsonify({"error": str(error)}), 503
    return jsonify({"recommendations": recommendations})


@app.route("/notes/<int:note_id>/delete", methods=["POST"])
def delete_note(note_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM study_notes WHERE id = ? AND user_id = ?",
        (note_id, session["user_id"]),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("notes"))


@app.route("/results", methods=["GET", "POST"])
def results():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        subject = request.form["subject"].strip()
        score = int(request.form["score"])
        total = int(request.form["total"])
        test_type = request.form["test_type"].strip()

        if subject and score >= 0 and total > 0:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO test_results (user_id, subject, score, total, test_type) VALUES (?, ?, ?, ?, ?)",
                (session["user_id"], subject, score, total, test_type),
            )
            conn.commit()
            conn.close()

        return redirect(url_for("results"))

    conn = get_db_connection()
    rows = conn.execute(
        "SELECT subject, score, total, test_type, created_at FROM test_results WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()

    chart_tests = [
        {
            "subject": row["subject"],
            "test_type": row["test_type"],
            "percentage": round((row["score"] / row["total"]) * 100, 1),
        }
        for row in reversed(rows[:10])
    ]

    total_tests = len(rows)
    avg_percentage = 0
    if rows:
        avg_percentage = round(sum((row["score"] / row["total"]) * 100 for row in rows) / total_tests, 1)

    subject_scores = {}
    for row in rows:
        subject = row["subject"]
        if subject not in subject_scores:
            subject_scores[subject] = {"total": 0, "score": 0, "count": 0}
        subject_scores[subject]["score"] += row["score"]
        subject_scores[subject]["total"] += row["total"]
        subject_scores[subject]["count"] += 1

    best_subject = None
    best_percent = 0
    for subject, data in subject_scores.items():
        percent = (data["score"] / data["total"]) * 100
        if percent > best_percent:
            best_percent = percent
            best_subject = subject

    conn.close()

    return render_template(
        "results.html",
        tests=rows,
        chart_tests=chart_tests,
        total_tests=total_tests,
        avg_percentage=avg_percentage,
        best_subject=best_subject,
        best_percent=best_percent,
    )


@app.route("/planner/<int:session_id>/delete", methods=["POST"])
def delete_session(session_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM study_sessions WHERE id = ? AND user_id = ?",
        (session_id, session["user_id"]),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("planner"))


@app.route("/goals/<int:goal_id>/toggle", methods=["POST"])
def toggle_goal(goal_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute(
        "UPDATE study_goals SET completed = CASE WHEN completed = 1 THEN 0 ELSE 1 END WHERE id = ? AND user_id = ?",
        (goal_id, session["user_id"]),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("goals"))


@app.route("/goals/<int:goal_id>/delete", methods=["POST"])
def delete_goal(goal_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM study_goals WHERE id = ? AND user_id = ?",
        (goal_id, session["user_id"]),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("goals"))


# Registration page
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        education = request.form["education"]
        course = request.form["course"].strip()

        if len(password) < 8:
            return render_template(
                "register.html",
                error="Password must contain at least 8 characters."
            )

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            conn.execute(
                """
                INSERT INTO students
                (name, email, password, education, course)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, email, hashed_password, education, course),
            )
            conn.commit()
            conn.close()

            return render_template(
                "register.html",
                success="Account created successfully! Welcome to StudyTrack."
            )

        except sqlite3.IntegrityError:
            return render_template(
                "register.html",
                error="This email is already registered."
            )

    return render_template("register.html")


if __name__ == "__main__":
    create_database()
    app.run(host="0.0.0.0", debug=False)