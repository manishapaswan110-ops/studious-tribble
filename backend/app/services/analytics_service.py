from ..models import Course, Flashcard, TestAttempt


def get_dashboard_summary(user_id):
    course_count = Course.query.filter_by(user_id=user_id).count()
    flashcard_count = Flashcard.query.filter_by(user_id=user_id).count()
    attempts = TestAttempt.query.filter_by(user_id=user_id).all()
    total_tests = len(attempts)
    avg_accuracy = round(
        sum(attempt.accuracy_percentage for attempt in attempts) / total_tests,
        2,
    ) if total_tests else 0.0

    return {
        "course_count": course_count,
        "flashcard_count": flashcard_count,
        "total_tests": total_tests,
        "average_accuracy": avg_accuracy,
        "latest_attempts": [attempt.to_dict() for attempt in attempts[-5:]],
    }
