from flask import Flask
from werkzeug.security import generate_password_hash

from config import Config
from models import Admin, db
from routes import main_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    app.register_blueprint(main_bp)
    register_commands(app)

    return app


def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        db.create_all()

        admin = Admin.query.filter_by(username=app.config["ADMIN_USERNAME"]).first()
        if not admin:
            admin = Admin(
                username=app.config["ADMIN_USERNAME"],
                password_hash=generate_password_hash(app.config["ADMIN_PASSWORD"]),
            )
            db.session.add(admin)
            db.session.commit()

        print("Database tables are ready.")


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
