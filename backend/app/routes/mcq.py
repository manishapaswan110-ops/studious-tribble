from datetime import datetime

from flask import Blueprint, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Question, Subject, Test, TestAttempt, Topic
from ..services.scoring_service import calculate_metrics, save_student_answers
from ..utils.helpers import error_response, success_response
from ..utils.validators import validate_record_ownership

mcq_bp = Blueprint("mcq", __name__)


@mcq_bp.route("/questions", methods=["GET"])
@login_required
def list_questions():
    subject_id = request.args.get("subject_id", type=int)
    topic_id = request.args.get("topic_id", type=int)
    if not subject_id:
        return error_response("subject_id is required.", 400)

    subject = Subject.query.get(subject_id)
    if subject is None or subject.user_id != current_user.id:
        return error_response("Subject not found for this user.", 404)

    query = Question.query.join(Topic, Topic.id == Question.topic_id).filter(Topic.subject_id == subject.id)
    if topic_id:
        query = query.filter(Question.topic_id == topic_id)
    questions = query.all()
    return success_response({"questions": [question.to_dict() for question in questions]}, 200)


@mcq_bp.route("/tests", methods=["POST"])
@login_required
def create_test():
    payload = request.get_json(silent=True) or {}
    test_name = (payload.get("test_name") or "").strip()
    subject_id = payload.get("subject_id")

    if not test_name or not subject_id:
        return error_response("test_name and subject_id are required.", 400)

    subject = Subject.query.get(subject_id)
    if subject is None or subject.user_id != current_user.id:
        return error_response("Subject not found for this user.", 404)

    test = Test(test_name=test_name, user_id=current_user.id, subject_id=subject.id)
    db.session.add(test)
    db.session.commit()
    return success_response({"test": test.to_dict()}, 201)


@mcq_bp.route("/tests/<int:test_id>/attempts", methods=["POST"])
@login_required
def start_test_attempt(test_id):
    test = validate_record_ownership(Test.query.get(test_id), current_user.id)
    payload = request.get_json(silent=True) or {}
    questions = Question.query.join(Topic, Topic.id == Question.topic_id).filter(Topic.subject_id == test.subject_id).all()
    question_ids = payload.get("question_ids") or [question.id for question in questions]
    question_ids = list(dict.fromkeys(question_ids))

    attempt = TestAttempt(
        test_id=test.id,
        user_id=current_user.id,
        total_questions=len(question_ids),
        attempted_questions=0,
        correct_answers=0,
        incorrect_answers=0,
        unanswered_questions=len(question_ids),
        marks_obtained=0.0,
        maximum_marks=0.0,
        accuracy_percentage=0.0,
        completed_at=datetime.utcnow(),
    )
    db.session.add(attempt)
    db.session.commit()
    return success_response({"attempt": attempt.to_dict()}, 201)


@mcq_bp.route("/tests/attempts/<int:attempt_id>/submit", methods=["POST"])
@login_required
def submit_attempt(attempt_id):
    attempt = validate_record_ownership(TestAttempt.query.get(attempt_id), current_user.id)
    payload = request.get_json(silent=True) or {}
    answers = payload.get("answers") or {}
    if not isinstance(answers, dict):
        return error_response("answers must be a dictionary keyed by question_id.", 400)

    normalized_answers = {}
    for key, value in answers.items():
        normalized_answers[int(key)] = value

    question_ids = []
    test = Test.query.get(attempt.test_id)
    if test is not None:
        question_ids = [
            question.id
            for question in Question.query.join(Topic, Topic.id == Question.topic_id)
            .filter(Topic.subject_id == test.subject_id)
            .all()
        ]

    metrics = calculate_metrics(question_ids, normalized_answers)
    save_student_answers(attempt, normalized_answers)

    attempt.total_questions = metrics["total_questions"]
    attempt.attempted_questions = metrics["attempted_questions"]
    attempt.correct_answers = metrics["correct_answers"]
    attempt.incorrect_answers = metrics["incorrect_answers"]
    attempt.unanswered_questions = metrics["unanswered_questions"]
    attempt.marks_obtained = metrics["marks_obtained"]
    attempt.maximum_marks = metrics["maximum_marks"]
    attempt.accuracy_percentage = metrics["accuracy_percentage"]
    attempt.completed_at = datetime.utcnow()
    db.session.commit()

    return success_response({"attempt": attempt.to_dict(), "metrics": metrics}, 200)


@mcq_bp.route("/tests/history", methods=["GET"])
@login_required
def list_test_history():
    attempts = TestAttempt.query.filter_by(user_id=current_user.id).order_by(TestAttempt.completed_at.desc()).all()
    return success_response({"history": [attempt.to_dict() for attempt in attempts]}, 200)
