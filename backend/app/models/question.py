from datetime import datetime

from ..extensions import db


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(10), nullable=False)
    explanation = db.Column(db.Text, nullable=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False)
    difficulty_level = db.Column(db.String(20), default="medium")
    marks = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    topic = db.relationship("Topic", back_populates="questions")

    def to_dict(self):
        return {
            "id": self.id,
            "question_text": self.question_text,
            "options": {
                "A": self.option_a,
                "B": self.option_b,
                "C": self.option_c,
                "D": self.option_d,
            },
            "correct_option": self.correct_option,
            "explanation": self.explanation,
            "topic_id": self.topic_id,
            "difficulty_level": self.difficulty_level,
            "marks": self.marks,
        }
