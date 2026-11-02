from datetime import date, timedelta

from ..models import FlashcardReview, TestAttempt, WeeklyReport
from ..extensions import db


def generate_weekly_report_for_user(user_id):
    today = date.today()
    week_start = today - timedelta(days=7)

    attempts = TestAttempt.query.filter(
        TestAttempt.user_id == user_id,
        TestAttempt.completed_at >= week_start,
    ).all()
    flashcards_reviewed = FlashcardReview.query.filter(
        FlashcardReview.user_id == user_id,
        FlashcardReview.reviewed_at >= week_start,
    ).count()

    average_accuracy = round(
        sum(attempt.accuracy_percentage for attempt in attempts) / len(attempts),
        2,
    ) if attempts else 0.0

    report = WeeklyReport(
        user_id=user_id,
        week_start_date=week_start,
        week_end_date=today,
        average_accuracy=average_accuracy,
        tests_completed=len(attempts),
        flashcards_reviewed=flashcards_reviewed,
    )
    db.session.add(report)
    db.session.commit()
    return report
