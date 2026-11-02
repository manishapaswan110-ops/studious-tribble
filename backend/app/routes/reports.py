from flask import Blueprint
from flask_login import current_user, login_required

from ..models import WeeklyReport
from ..services.weekly_report_service import generate_weekly_report_for_user
from ..utils.helpers import success_response

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/reports/weekly", methods=["GET"])
@login_required
def weekly_reports():
    report = generate_weekly_report_for_user(current_user.id)
    return success_response({"report": report.to_dict()}, 200)


@reports_bp.route("/reports", methods=["GET"])
@login_required
def report_history():
    reports = WeeklyReport.query.filter_by(user_id=current_user.id).order_by(WeeklyReport.created_at.desc()).all()
    return success_response({"reports": [r.to_dict() for r in reports]}, 200)
