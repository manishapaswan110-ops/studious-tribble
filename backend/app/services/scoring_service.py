from ..models import Question, StudentAnswer


def calculate_metrics(question_ids, answers_by_question):
    questions = Question.query.filter(Question.id.in_(question_ids)).all() if question_ids else []
    by_id = {question.id: question for question in questions}
    total_questions = len(question_ids)
    attempted = 0
    correct_answers = 0
    incorrect_answers = 0
    unanswered_questions = 0
    marks_obtained = 0.0
    maximum_marks = sum(question.marks for question in questions)

    for question_id in question_ids:
        selected = answers_by_question.get(question_id)
        if selected is None or str(selected).strip() == "":
            unanswered_questions += 1
            continue

        attempted += 1
        question = by_id.get(question_id)
        if question is None:
            incorrect_answers += 1
            continue

        selected_option = str(selected).strip().upper()
        is_correct = selected_option == str(question.correct_option).strip().upper()
        if is_correct:
            correct_answers += 1
            marks_obtained += float(question.marks)
        else:
            incorrect_answers += 1

    accuracy_percentage = 0.0
    if attempted:
        accuracy_percentage = round((correct_answers / attempted) * 100, 2)

    return {
        "total_questions": total_questions,
        "attempted_questions": attempted,
        "correct_answers": correct_answers,
        "incorrect_answers": incorrect_answers,
        "unanswered_questions": unanswered_questions,
        "marks_obtained": round(marks_obtained, 2),
        "maximum_marks": round(float(maximum_marks), 2),
        "accuracy_percentage": accuracy_percentage,
    }


def save_student_answers(attempt, answers_by_question):
    saved_answers = []
    for question_id, selected_option in answers_by_question.items():
        question = Question.query.get(question_id)
        if question is None:
            continue

        selected_value = str(selected_option).strip().upper() if selected_option is not None else None
        is_correct = selected_value == str(question.correct_option).strip().upper() if selected_value else False
        marks_awarded = float(question.marks) if is_correct else 0.0

        answer = StudentAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            selected_option=selected_value,
            is_correct=is_correct,
            marks_awarded=marks_awarded,
        )
        from ..extensions import db

        db.session.add(answer)
        saved_answers.append(answer)

    return saved_answers
