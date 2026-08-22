import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base
from app.api.deps import get_db


TEST_DATABASE_URL = "postgresql://saas_user:saas_password@localhost:5433/saas_db_test"


engine = create_engine(TEST_DATABASE_URL)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

_email_counter = {"n": 0}


def _unique_email():
    _email_counter["n"] += 1
    return f"user{_email_counter['n']}@example.com"


@pytest.fixture
def register_user(client):
    """
    Factory fixture. Call it to register + log in a brand new user and get
    back everything a test needs to act as that user:

        user = register_user()
        client.post("/projects", json={...}, headers=user["headers"])

    Each call creates a distinct user, so it's the building block for any
    two-tenant ownership test.
    """

    def _register(email: str | None = None, password: str = "supersecret123"):
        email = email or _unique_email()

        register_resp = client.post(
            "/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": "Test User",
                "company_name": "Test Co",
                "default_currency": "USD",
                "timezone": "UTC",
            },
        )
        assert register_resp.status_code == 200, register_resp.text

        login_resp = client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 200, login_resp.text
        access_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        me = client.get("/me", headers=headers)
        assert me.status_code == 200, me.text

        return {
            "email": email,
            "password": password,
            "id": me.json()["id"],
            "headers": headers,
            "access_token": access_token,
        }

    return _register


@pytest.fixture
def user_a(register_user):
    return register_user()


@pytest.fixture
def user_b(register_user):
    return register_user()


@pytest.fixture
def authenticated_client(client, user_a):
    """Back-compat: a client already authenticated as a single test user."""
    return client