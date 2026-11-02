from datetime import datetime

from ..extensions import db


class Test(db.Model):
    __tablename__ = "tests"

    id = db.Column(db.Integer, primary_key=True)
    test_name = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="tests")
    subject = db.relationship("Subject", back_populates="tests")
    attempts = db.relationship("TestAttempt", back_populates="test", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "test_name": self.test_name,
            "user_id": self.user_id,
            "subject_id": self.subject_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TestAttempt(db.Model):
    __tablename__ = "test_attempts"

    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey("tests.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    total_questions = db.Column(db.Integer, default=0, nullable=False)
    attempted_questions = db.Column(db.Integer, default=0, nullable=False)
    correct_answers = db.Column(db.Integer, default=0, nullable=False)
    incorrect_answers = db.Column(db.Integer, default=0, nullable=False)
    unanswered_questions = db.Column(db.Integer, default=0, nullable=False)
    marks_obtained = db.Column(db.Float, default=0.0, nullable=False)
    maximum_marks = db.Column(db.Float, default=0.0, nullable=False)
    accuracy_percentage = db.Column(db.Float, default=0.0, nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    test = db.relationship("Test", back_populates="attempts")
    user = db.relationship("User", back_populates="test_attempts")
    answers = db.relationship("StudentAnswer", back_populates="attempt", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "test_id": self.test_id,
            "user_id": self.user_id,
            "total_questions": self.total_questions,
            "attempted_questions": self.attempted_questions,
            "correct_answers": self.correct_answers,
            "incorrect_answers": self.incorrect_answers,
            "unanswered_questions": self.unanswered_questions,
            "marks_obtained": self.marks_obtained,
            "maximum_marks": self.maximum_marks,
            "accuracy_percentage": self.accuracy_percentage,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class StudentAnswer(db.Model):
    __tablename__ = "student_answers"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("test_attempts.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    selected_option = db.Column(db.String(10), nullable=True)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    marks_awarded = db.Column(db.Float, default=0.0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    attempt = db.relationship("TestAttempt", back_populates="answers")
    question = db.relationship("Question")

    def to_dict(self):
        return {
            "id": self.id,
            "attempt_id": self.attempt_id,
            "question_id": self.question_id,
            "selected_option": self.selected_option,
            "is_correct": self.is_correct,
            "marks_awarded": self.marks_awarded,
        }
