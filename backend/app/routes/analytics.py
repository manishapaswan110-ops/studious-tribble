from flask import Blueprint
from flask_login import current_user, login_required

from ..services.analytics_service import get_dashboard_summary
from ..services.recommendation_service import generate_recommendations
from ..utils.helpers import success_response

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/analytics/summary", methods=["GET"])
@login_required
def analytics_summary():
    return success_response({
        "summary": get_dashboard_summary(current_user.id),
        "recommendations": generate_recommendations(current_user.id),
    }, 200)
