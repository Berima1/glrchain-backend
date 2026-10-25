import os
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

os.environ.setdefault("GLRCHAIN_CREATE_SCHEMA_ON_STARTUP", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-glrchain-key-not-for-deployment-001122334455")
os.environ.setdefault("REPORT_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./glrchain_test.db")

from app.main import app
from app.routes import auth as auth_routes


def test_firebase_provisioning_uses_verified_uid_and_disables_password_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLRCHAIN_AUTH_PROVIDER", "firebase")
    uid = "firebase-test-" + uuid4().hex

    async def fake_verify(_token: str) -> dict:
        return {"uid": uid, "email": "test-user@example.invalid"}

    monkeypatch.setattr(auth_routes, "_verify_firebase_token", fake_verify)

    with TestClient(app) as client:
        headers = {"Authorization": "Bearer unit-test-id-token"}
        username = "firebase_" + uuid4().hex[:16]
        response = client.post("/auth/provision", headers=headers, json={"username": username})
        assert response.status_code == 200, response.text
        assert response.json()["role"] == "user"

        identity = client.get("/auth/me", headers=headers)
        assert identity.status_code == 200, identity.text
        assert identity.json()["username"] == username
        assert identity.json()["id"] == response.json()["id"]

        retry = client.post("/auth/provision", headers=headers, json={"username": "unused-retry"})
        assert retry.status_code == 200
        assert retry.json()["id"] == response.json()["id"]

        password_login = client.post(
            "/auth/login",
            json={"username": username, "password": "not-used-in-firebase-mode"},
        )
        assert password_login.status_code == 410
