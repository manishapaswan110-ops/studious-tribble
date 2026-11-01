
import os
import secrets
import sqlite3
from datetime import date

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)


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
    conn.commit()
    conn.close()


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
    goals = conn.execute(
        "SELECT id, title, target_date, completed FROM study_goals WHERE user_id = ? ORDER BY completed ASC, target_date ASC LIMIT 3",
        (session["user_id"],),
    ).fetchall()
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

    return render_template("dashboard.html", user=user, progress=progress, goals=goals)


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
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
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

        conn.close()
        return redirect(url_for("profile"))

    conn.close()
    return render_template("profile.html", user=user)


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
    conn.close()

    return render_template("notes.html", notes=note_list)


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
    app.run(debug=True)