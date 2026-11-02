import pytest

from run import app
from backend.app.extensions import db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    with app.app_context():
        db.drop_all()
        db.create_all()

    with app.test_client() as client:
        yield client

    with app.app_context():
        db.drop_all()


def test_register_and_get_profile(client):
    response = client.post(
        "/api/auth/register",
        json={"full_name": "Alice Example", "email": "alice@example.com", "password": "secret123"},
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["user"]["email"] == "alice@example.com"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"]["full_name"] == "Alice Example"


def test_course_subject_topic_flow(client):
    client.post("/api/auth/register", json={"full_name": "Alice", "email": "alice@example.com", "password": "secret123"})

    course_resp = client.post("/api/courses", json={"course_name": "Mathematics"})
    assert course_resp.status_code == 201
    course_id = course_resp.get_json()["course"]["id"]

    subject_resp = client.post("/api/subjects", json={"course_id": course_id, "subject_name": "Algebra"})
    assert subject_resp.status_code == 201
    subject_id = subject_resp.get_json()["subject"]["id"]

    topic_resp = client.post("/api/topics", json={"subject_id": subject_id, "topic_name": "Linear Equations"})
    assert topic_resp.status_code == 201
    assert topic_resp.get_json()["topic"]["topic_name"] == "Linear Equations"


def test_mcq_attempt_submission(client):
    client.post("/api/auth/register", json={"full_name": "Alice", "email": "alice@example.com", "password": "secret123"})
    client.post("/api/courses", json={"course_name": "Science"})
    client.post("/api/subjects", json={"course_id": 1, "subject_name": "Physics"})
    client.post("/api/topics", json={"subject_id": 1, "topic_name": "Motion"})

    from backend.app.extensions import db
    from backend.app.models import Question, Topic

    with app.app_context():
        topic = Topic.query.first()
        question = Question(
            question_text="Which unit is used to measure speed?",
            option_a="kg",
            option_b="m/s",
            option_c="N",
            option_d="J",
            correct_option="B",
            explanation="Speed is measured in meters per second.",
            topic_id=topic.id,
            difficulty_level="easy",
            marks=3,
        )
        db.session.add(question)
        db.session.commit()

    test_resp = client.post("/api/tests", json={"test_name": "Speed Quiz", "subject_id": 1})
    assert test_resp.status_code == 201

    attempt_resp = client.post("/api/tests/1/attempts", json={})
    assert attempt_resp.status_code == 201

    submit_resp = client.post("/api/tests/attempts/1/submit", json={"answers": {"1": "B"}})
    assert submit_resp.status_code == 200
    assert submit_resp.get_json()["attempt"]["accuracy_percentage"] == 100.0
