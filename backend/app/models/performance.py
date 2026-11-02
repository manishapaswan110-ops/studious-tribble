from datetime import datetime

from ..extensions import db


class WeeklyReport(db.Model):
    __tablename__ = "weekly_reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    week_start_date = db.Column(db.Date, nullable=False)
    week_end_date = db.Column(db.Date, nullable=False)
    average_accuracy = db.Column(db.Float, default=0.0, nullable=False)
    tests_completed = db.Column(db.Integer, default=0, nullable=False)
    flashcards_reviewed = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="weekly_reports")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "week_start_date": self.week_start_date.isoformat() if self.week_start_date else None,
            "week_end_date": self.week_end_date.isoformat() if self.week_end_date else None,
            "average_accuracy": self.average_accuracy,
            "tests_completed": self.tests_completed,
            "flashcards_reviewed": self.flashcards_reviewed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
