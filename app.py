import os
from datetime import datetime, date
from pathlib import Path
from flask import Flask, render_template, jsonify

from config import config_by_name, BASE_DIR
from models.database import db
from models.meeting import Meeting
from models.action_item import ActionItem
from routes import main_bp, meetings_bp, action_items_bp, api_bp


def create_app(config_name: str = None) -> Flask:
    """
    Application factory for the AI Meeting Action-Item Extractor.
    Initializes database, registers blueprints, filters, and error handlers.
    """
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development").lower()

    app = Flask(__name__)
    config_obj = config_by_name.get(config_name, config_by_name["development"])
    app.config.from_object(config_obj)

    # Ensure required folders exist
    uploads_dir = Path(app.config.get("UPLOAD_FOLDER", BASE_DIR / "uploads"))
    exports_dir = Path(app.config.get("EXPORT_FOLDER", BASE_DIR / "exports"))
    uploads_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(meetings_bp)
    app.register_blueprint(action_items_bp)
    app.register_blueprint(api_bp)

    # Register custom Jinja template filters
    @app.template_filter("status_badge")
    def status_badge_filter(status: str) -> str:
        s = (status or "").lower()
        if s == "completed":
            return "badge-completed"
        elif s == "overdue":
            return "badge-overdue"
        return "badge-pending"

    @app.template_filter("confidence_badge")
    def confidence_badge_filter(confidence_val) -> str:
        try:
            val = float(confidence_val)
            pct = val * 100 if val <= 1.0 else val
            if pct >= 75:
                return "badge-confidence-high"
            elif pct >= 50:
                return "badge-confidence-med"
            return "badge-confidence-low"
        except (ValueError, TypeError):
            return "badge-confidence-med"

    @app.template_filter("format_date")
    def format_date_filter(val, fmt="%b %d, %Y") -> str:
        if not val:
            return "Not specified"
        if isinstance(val, (datetime, date)):
            return val.strftime(fmt)
        return str(val)

    # Global context processors for templates
    @app.context_processor
    def inject_global_data():
        return {
            "current_year": datetime.utcnow().year,
            "app_name": "ActionAI",
            "app_full_name": "AI Meeting Action-Item Extractor"
        }

    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        if request_wants_json():
            return jsonify({"error": "Resource not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        if request_wants_json():
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(413)
    def request_entity_too_large(e):
        if request_wants_json():
            return jsonify({"error": "File size exceeds maximum allowable limit (16MB)"}), 413
        return render_template("errors/413.html"), 413

    def request_wants_json():
        from flask import request
        return (
            request.is_json or
            request.path.startswith("/api/") or
            request.headers.get("Accept") == "application/json"
        )

    # Create tables automatically
    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
