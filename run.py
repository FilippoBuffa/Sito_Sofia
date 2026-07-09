from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models import User
from app.models.user import TestService

app = create_app("development")


def seed_db():
    """Create default users and test services if not present."""
    with app.app_context():
        db.create_all()

        # Test services
        air_flow = TestService.query.filter_by(name="Air Flow Test").first()
        if not air_flow:
            air_flow = TestService(
                name="Air Flow Test",
                description="Functional air flow testing for checkvalve characterization.",
            )
            db.session.add(air_flow)

        water_flow = TestService.query.filter_by(name="Water Flow Test").first()
        if not water_flow:
            water_flow = TestService(
                name="Water Flow Test",
                description="Functional water flow testing for checkvalve characterization.",
            )
            db.session.add(water_flow)

        db.session.flush()

        # Client user (seed — email pre-verified)
        if not User.query.filter_by(username="admin").first():
            client = User(
                username="admin",
                email="admin@vernay.com",
                first_name="Admin",
                last_name="User",
                role="client",
                email_verified=True,
            )
            client.set_password("admin")
            db.session.add(client)

        # Engineer user (seed — email pre-verified)
        if not User.query.filter_by(username="test_eng").first():
            engineer = User(
                username="test_eng",
                email="test_eng@vernay.com",
                first_name="Test",
                last_name="Engineer",
                role="engineer",
                email_verified=True,
            )
            engineer.set_password("test_eng")
            engineer.services = [air_flow, water_flow]
            db.session.add(engineer)

        db.session.commit()
        print("Database seeded.")


if __name__ == "__main__":
    seed_db()
    app.run(debug=True, host="0.0.0.0", port=8080)
