from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from ..services.analytics_service import get_dashboard_summary


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    return jsonify({
        "user": current_user.to_dict(),
        "summary": get_dashboard_summary(current_user.id),
    })
