import sqlite3
from io import BytesIO
from types import SimpleNamespace

import pytest

import app as study_app
import ai_service


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    study_app.app.config["TESTING"] = True
    study_app.create_database()
    with study_app.app.test_client() as test_client:
        yield test_client


def register(client, name, email):
    response = client.post(
        "/register",
        data={
            "name": name,
            "email": email,
            "password": "secure-password",
            "education": "College",
            "course": "Science",
        },
    )
    assert response.status_code == 200
    response = client.post(
        "/login",
        data={"email": email, "password": "secure-password"},
    )
    assert response.status_code == 302


def add_note(user_id, title="Biology", content="Cells are the basic units of life."):
    conn = sqlite3.connect("studytrack.db")
    cursor = conn.execute(
        "INSERT INTO study_notes (user_id, title, content) VALUES (?, ?, ?)",
        (user_id, title, content),
    )
    note_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return note_id


def ai_headers(client):
    with client.session_transaction() as session:
        token = session["_ai_csrf_token"]
    return {"X-CSRF-Token": token}


def test_ai_endpoints_require_login(client):
    response = client.post("/ai/summarize", json={"text": "Study material"})
    assert response.status_code == 401


def test_ai_post_requires_csrf_token(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    note_id = add_note(1)
    monkeypatch.setattr(study_app, "summarize_notes", lambda title, content: "Summary")

    response = client.post("/ai/summarize", json={"note_id": note_id})
    assert response.status_code == 403


def test_missing_openai_key_returns_configuration_error(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    note_id = add_note(1)
    client.get("/notes")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.post(
        "/ai/summarize",
        json={"note_id": note_id},
        headers=ai_headers(client),
    )
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.get_json()["error"]


def test_ai_service_uses_configured_openai_client(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            message = SimpleNamespace(content='{"summary":"A concise summary."}')
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "OpenAI", FakeOpenAI)

    assert ai_service.summarize_notes("Biology", "Cell notes.") == "A concise summary."
    assert captured["client"]["api_key"] == "test-key"
    assert captured["response_format"] == {"type": "json_object"}


def test_quiz_can_be_generated_from_a_topic(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    client.get("/notes")
    quiz = [{
        "question": "What is x if x + 2 = 4?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
        "correct_option": "B",
        "explanation": "Subtract 2 from both sides.",
    }]
    monkeypatch.setattr(study_app, "generate_quiz", lambda title, content, count: quiz)

    response = client.post(
        "/ai/quiz",
        json={"topic": "Linear equations", "count": 1},
        headers=ai_headers(client),
    )
    assert response.status_code == 200
    assert response.get_json()["questions"][0]["correct_option"] == "B"


def test_student_can_start_and_submit_mcq_test(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    client.get("/start-test")
    questions = [{
        "question": "What is the basic unit of life?",
        "options": {"A": "Atom", "B": "Cell", "C": "Organ", "D": "Tissue"},
        "correct_option": "B",
        "explanation": "Cells are the basic units of life.",
    }]
    monkeypatch.setattr(
        study_app,
        "generate_test_questions",
        lambda title, content, question_type, count: questions,
    )

    started = client.post(
        "/ai/start-test",
        json={
            "subject": "Biology",
            "text": "Cells are the basic units of life.",
            "question_type": "mcq",
            "count": 1,
        },
        headers=ai_headers(client),
    )
    assert started.status_code == 201
    test_data = started.get_json()
    assert "correct_option" not in test_data["questions"][0]

    submitted = client.post(
        "/ai/submit-test",
        json={"test_id": test_data["test_id"], "answers": {"0": "B"}},
        headers=ai_headers(client),
    )
    assert submitted.status_code == 200
    assert submitted.get_json()["score"] == 1
    assert submitted.get_json()["percentage"] == 100.0
    assert submitted.get_json()["results"][0]["correct"] is True

    duplicate = client.post(
        "/ai/submit-test",
        json={"test_id": test_data["test_id"], "answers": {"0": "B"}},
        headers=ai_headers(client),
    )
    assert duplicate.status_code == 409


def test_fill_blank_test_accepts_answers_and_saves_result(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    client.get("/start-test")
    questions = [{"prompt": "The basic unit of life is the ____.", "accepted_answers": ["cell", "a cell"]}]
    monkeypatch.setattr(
        study_app,
        "generate_test_questions",
        lambda title, content, question_type, count: questions,
    )

    started = client.post(
        "/ai/start-test",
        json={
            "subject": "Biology",
            "text": "Cells are the basic units of life.",
            "question_type": "fill_blank",
            "count": 1,
        },
        headers=ai_headers(client),
    )
    test_id = started.get_json()["test_id"]
    submitted = client.post(
        "/ai/submit-test",
        json={"test_id": test_id, "answers": {"0": " A CELL! "}},
        headers=ai_headers(client),
    )

    assert submitted.status_code == 200
    assert submitted.get_json()["results"][0]["correct"] is True
    conn = sqlite3.connect("studytrack.db")
    result = conn.execute(
        "SELECT subject, score, total, test_type FROM test_results WHERE user_id = 1"
    ).fetchone()
    conn.close()
    assert result == ("Biology", 1, 1, "AI Fill Blank")


def test_unanswered_mcq_is_not_marked_as_the_first_choice(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    client.get("/start-test")
    monkeypatch.setattr(
        study_app,
        "generate_test_questions",
        lambda title, content, question_type, count: [{
            "question": "What is the basic unit of life?",
            "options": {"A": "Atom", "B": "Cell", "C": "Organ", "D": "Tissue"},
            "correct_option": "A",
            "explanation": "An atom is the basic unit of matter.",
        }],
    )

    started = client.post(
        "/ai/start-test",
        json={
            "subject": "Biology",
            "text": "Atoms form matter.",
            "question_type": "mcq",
            "count": 1,
        },
        headers=ai_headers(client),
    )
    submitted = client.post(
        "/ai/submit-test",
        json={"test_id": started.get_json()["test_id"], "answers": {"0": ""}},
        headers=ai_headers(client),
    )

    assert submitted.status_code == 200
    assert submitted.get_json()["score"] == 0
    assert submitted.get_json()["results"][0]["correct"] is False


def test_short_answers_are_ai_graded_and_test_attempt_is_owner_scoped(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    client.get("/start-test")
    questions = [{
        "question": "What do cells do?",
        "expected_answer": "Cells are the basic units of living organisms.",
        "rubric": "Identifies cells as fundamental units of life.",
    }]
    monkeypatch.setattr(
        study_app,
        "generate_test_questions",
        lambda title, content, question_type, count: questions,
    )
    monkeypatch.setattr(
        study_app,
        "grade_short_answers",
        lambda responses: [{"correct": True, "feedback": "Correct; you identified their role."}],
    )

    started = client.post(
        "/ai/start-test",
        json={
            "subject": "Biology",
            "text": "Cells are the basic units of life.",
            "question_type": "short_answer",
            "count": 1,
        },
        headers=ai_headers(client),
    )
    test_id = started.get_json()["test_id"]
    client.get("/logout")
    register(client, "Bob", "bob@example.com")
    client.get("/start-test")
    denied = client.post(
        "/ai/submit-test",
        json={"test_id": test_id, "answers": {"0": "They are the building blocks of life."}},
        headers=ai_headers(client),
    )
    assert denied.status_code == 404

    client.get("/logout")
    client.post("/login", data={"email": "alice@example.com", "password": "secure-password"})
    client.get("/start-test")
    submitted = client.post(
        "/ai/submit-test",
        json={"test_id": test_id, "answers": {"0": "They are the building blocks of life."}},
        headers=ai_headers(client),
    )
    assert submitted.status_code == 200
    assert submitted.get_json()["score"] == 1


def test_note_summary_and_owner_isolation(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    note_id = add_note(1)
    monkeypatch.setattr(study_app, "summarize_notes", lambda title, content: "A cell is life's basic unit.")
    client.get("/notes")

    response = client.post("/ai/summarize", json={"note_id": note_id}, headers=ai_headers(client))
    assert response.status_code == 200
    assert response.get_json()["summary"] == "A cell is life's basic unit."

    client.get("/logout")
    register(client, "Bob", "bob@example.com")
    client.get("/logout")
    client.post("/login", data={"email": "alice@example.com", "password": "secure-password"})
    client.get("/notes")
    other_user_note_id = add_note(2, "Private", "Another student's private notes.")
    response = client.post("/ai/summarize", json={"note_id": other_user_note_id}, headers=ai_headers(client))
    assert response.status_code == 404


def test_generated_flashcards_are_saved_to_the_current_user(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    note_id = add_note(1)
    client.get("/notes")
    cards = [{"question": "What is a cell?", "answer": "The basic unit of life."}]
    monkeypatch.setattr(study_app, "generate_flashcards", lambda title, content, count: cards)

    generated = client.post(
        "/ai/flashcards",
        json={"note_id": note_id, "count": 1},
        headers=ai_headers(client),
    )
    assert generated.status_code == 201
    assert generated.get_json()["saved"] is True

    saved = client.get("/ai/flashcards")
    assert saved.status_code == 200
    assert saved.get_json()["flashcards"][0]["question"] == "What is a cell?"


def test_recommendations_use_current_user_results(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    conn = sqlite3.connect("studytrack.db")
    conn.execute(
        "INSERT INTO test_results (user_id, subject, score, total, test_type) VALUES (1, 'Biology', 7, 10, 'Quiz')"
    )
    conn.commit()
    conn.close()

    captured = {}

    def fake_recommendations(performance):
        captured.update(performance)
        return [{"title": "Review cells", "reason": "Your score can improve.", "action": "Revisit your notes."}]

    monkeypatch.setattr(study_app, "generate_recommendations", fake_recommendations)
    client.get("/notes")
    response = client.post("/ai/recommendations", json={}, headers=ai_headers(client))

    assert response.status_code == 200
    assert captured["assessment_count"] == 1
    assert captured["subjects"][0]["average_percentage"] == 70.0


def test_syllabus_upload_generates_and_saves_subject_notes(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    response = client.post(
        "/profile",
        data={
            "name": "Alice",
            "education": "Undergraduate",
            "course": "Biology",
            "subjects": "Biology\nChemistry",
            "syllabus_text": "",
            "syllabus_file": (
                BytesIO(b"Biology syllabus: cell structure, organelles, and cell division."),
                "biology-syllabus.txt",
            ),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    client.get("/notes")

    captured = {}

    def fake_generate_notes(course, education, subject, syllabus):
        captured.update({
            "course": course,
            "education": education,
            "subject": subject,
            "syllabus": syllabus,
        })
        return {
            "title": "Cell Structure",
            "notes": "## Cell membrane\nControls movement into and out of the cell.",
        }

    monkeypatch.setattr(study_app, "generate_syllabus_notes", fake_generate_notes)
    generated = client.post(
        "/ai/syllabus-notes",
        json={"subject": "Biology"},
        headers=ai_headers(client),
    )

    assert generated.status_code == 201
    assert captured["course"] == "Biology"
    assert captured["subject"] == "Biology"
    assert "cell division" in captured["syllabus"]
    assert generated.get_json()["note"]["title"] == "Biology - Cell Structure"

    conn = sqlite3.connect("studytrack.db")
    saved_note = conn.execute(
        "SELECT title, content FROM study_notes WHERE user_id = 1"
    ).fetchone()
    conn.close()
    assert saved_note == (
        "Biology - Cell Structure",
        "## Cell membrane\nControls movement into and out of the cell.",
    )

    client.get("/logout")
    register(client, "Bob", "bob@example.com")
    client.get("/notes")
    unavailable = client.post(
        "/ai/syllabus-notes",
        json={"subject": "Biology"},
        headers=ai_headers(client),
    )
    assert unavailable.status_code == 400
    assert "Add your syllabus" in unavailable.get_json()["error"]


def test_dashboard_personalizes_syllabus_and_practice_actions(client):
    register(client, "Alice", "alice@example.com")
    conn = sqlite3.connect("studytrack.db")
    conn.execute(
        "INSERT INTO student_subjects (user_id, subject_name) VALUES (1, 'Biology')"
    )
    conn.execute(
        "INSERT INTO student_subjects (user_id, subject_name) VALUES (1, 'Chemistry')"
    )
    conn.execute(
        "INSERT INTO student_syllabi (user_id, syllabus_text) VALUES (1, 'Biology: cells; Chemistry: atoms')"
    )
    conn.execute(
        "INSERT INTO test_results (user_id, subject, score, total, test_type) VALUES (1, 'Biology', 6, 10, 'Quiz')"
    )
    conn.execute(
        "INSERT INTO test_results (user_id, subject, score, total, test_type) VALUES (1, 'Chemistry', 9, 10, 'Quiz')"
    )
    conn.commit()
    conn.close()

    dashboard = client.get("/dashboard")
    page = dashboard.get_data(as_text=True)
    assert dashboard.status_code == 200
    assert "Your syllabus is saved" in page
    assert "Biology" in page
    assert "60.0% average" in page
    assert "Get syllabus notes" in page

    test_page = client.get("/start-test?subject=Biology")
    assert test_page.status_code == 200
    assert '<option value="Biology" selected>' in test_page.get_data(as_text=True)


def test_dashboard_prompts_user_without_syllabus_to_add_one(client):
    register(client, "Alice", "alice@example.com")

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Add my syllabus" in response.get_data(as_text=True)


def test_start_test_page_explains_missing_openai_configuration(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.get("/start-test")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "AI question generation is not configured" in page
    assert 'id="start-button" disabled' in page


def test_notes_page_shows_ai_setup_warning_when_key_is_missing(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.get("/notes")

    assert response.status_code == 200
    assert "AI is not connected yet" in response.get_data(as_text=True)


def test_notes_page_enables_ai_actions_when_key_is_configured(client, monkeypatch):
    register(client, "Alice", "alice@example.com")
    monkeypatch.setenv("OPENAI_API_KEY", "configured-test-key")

    response = client.get("/notes")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "AI is not connected yet" not in page
    assert 'id="recommendations-button"' in page
    assert 'id="recommendations-button" disabled' not in page
