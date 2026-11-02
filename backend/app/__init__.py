from flask import Flask

from .config import BaseConfig
from .extensions import csrf, db, login_manager
from .models import User
from .routes.analytics import analytics_bp
from .routes.auth import auth_bp
from .routes.courses import courses_bp
from .routes.dashboard import dashboard_bp
from .routes.flashcards import flashcards_bp
from .routes.mcq import mcq_bp
from .routes.reports import reports_bp
from .routes.subjects import subjects_bp
from .routes.topics import topics_bp


def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(BaseConfig)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/api")
    app.register_blueprint(courses_bp, url_prefix="/api")
    app.register_blueprint(subjects_bp, url_prefix="/api")
    app.register_blueprint(topics_bp, url_prefix="/api")
    app.register_blueprint(mcq_bp, url_prefix="/api")
    app.register_blueprint(flashcards_bp, url_prefix="/api")
    app.register_blueprint(analytics_bp, url_prefix="/api")
    app.register_blueprint(reports_bp, url_prefix="/api")

    csrf.exempt(auth_bp)
    csrf.exempt(dashboard_bp)
    csrf.exempt(courses_bp)
    csrf.exempt(subjects_bp)
    csrf.exempt(topics_bp)
    csrf.exempt(mcq_bp)
    csrf.exempt(flashcards_bp)
    csrf.exempt(analytics_bp)
    csrf.exempt(reports_bp)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    login_manager.login_view = "auth.login"

    with app.app_context():
        db.create_all()

    return app
