from flask import Blueprint, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Course
from ..utils.helpers import error_response, success_response
from ..utils.validators import validate_record_ownership

courses_bp = Blueprint("courses", __name__)


@courses_bp.route("/courses", methods=["GET"])
@login_required
def list_courses():
    courses = Course.query.filter_by(user_id=current_user.id).order_by(Course.created_at.desc()).all()
    return success_response({"courses": [course.to_dict() for course in courses]}, 200)


@courses_bp.route("/courses", methods=["POST"])
@login_required
def create_course():
    payload = request.get_json(silent=True) or {}
    course_name = (payload.get("course_name") or "").strip()
    description = (payload.get("description") or "").strip()

    if not course_name:
        return error_response("course_name is required.", 400)

    course = Course(course_name=course_name, description=description, user_id=current_user.id)
    db.session.add(course)
    db.session.commit()
    return success_response({"course": course.to_dict()}, 201)


@courses_bp.route("/courses/<int:course_id>", methods=["PUT"])
@login_required
def update_course(course_id):
    course = validate_record_ownership(Course.query.get(course_id), current_user.id)
    payload = request.get_json(silent=True) or {}
    course.course_name = (payload.get("course_name") or course.course_name).strip()
    course.description = (payload.get("description") or course.description or "").strip()
    db.session.commit()
    return success_response({"course": course.to_dict()}, 200)


@courses_bp.route("/courses/<int:course_id>", methods=["DELETE"])
@login_required
def delete_course(course_id):
    course = validate_record_ownership(Course.query.get(course_id), current_user.id)
    db.session.delete(course)
    db.session.commit()
    return success_response({"message": "Course deleted successfully."}, 200)
