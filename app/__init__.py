from flask import Flask, redirect, url_for
from flask_login import current_user
from .config import config
from .extensions import db, login_manager, migrate, csrf, mail


def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    mail.init_app(app)

    # Register blueprints
    from .blueprints.auth import bp as auth_bp
    from .blueprints.client import bp as client_bp
    from .blueprints.engineer import bp as engineer_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(engineer_bp)

    # Root redirect
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.is_engineer:
                return redirect(url_for("engineer.dashboard"))
            return redirect(url_for("client.dashboard"))
        return redirect(url_for("auth.login"))

    # 403 handler
    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("errors/403.html"), 403

    # 404 handler
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("errors/404.html"), 404

    return app
