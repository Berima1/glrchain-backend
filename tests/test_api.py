import os
import sqlite3
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

os.environ.setdefault("GLRCHAIN_CREATE_SCHEMA_ON_STARTUP", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-glrchain-key-not-for-deployment-001122334455")
os.environ.setdefault("REPORT_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./glrchain_test.db")

from fastapi.testclient import TestClient

from app.main import app
from app.database import database_url_from_env, normalize_database_url


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _create_account(client: TestClient) -> tuple[str, str]:
    username = "test_" + uuid4().hex[:20]
    password = "Strong-CI-passphrase-1"
    registration = client.post(
        "/auth/register",
        json={"username": username, "password": password, "role": "admin"},
    )
    assert registration.status_code == 201, registration.text
    assert registration.json()["role"] == "user"

    login = client.post("/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    assert login.json()["token_type"] == "bearer"
    assert login.json()["expires_in"] > 0
    return username, token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _stored_description(report_id: int) -> tuple[str, int]:
    url = os.environ["DATABASE_URL"]
    if url.startswith("sqlite+aiosqlite:///"):
        path = url.split("sqlite+aiosqlite:///", 1)[1]
        with sqlite3.connect(path) as connection:
            row = connection.execute(
                "SELECT description, encryption_key_version FROM reports WHERE id = ?",
                (report_id,),
            ).fetchone()
    else:
        import psycopg2

        sync_url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        with psycopg2.connect(sync_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT description, encryption_key_version FROM reports WHERE id = %s",
                    (report_id,),
                )
                row = cursor.fetchone()
    assert row is not None
    return row[0], row[1]


def test_health_endpoints(client: TestClient) -> None:
    assert client.get("/health/live").status_code == 200
    ready = client.get("/health/ready")
    assert ready.status_code == 200, ready.text
    assert ready.json() == {"status": "ready", "database": "ok"}


def test_registration_login_and_public_role_cannot_escalate(client: TestClient) -> None:
    username, token = _create_account(client)
    response = client.get("/auth/me", headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["username"] == username
    assert response.json()["role"] == "user"

    forbidden = client.get("/admin/stats", headers=_headers(token))
    assert forbidden.status_code == 403


def test_report_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/reports",
        json={
            "location": "Eastern Region, Ghana",
            "description": "A sufficiently long report description for security testing.",
        },
    )
    assert response.status_code == 401


def test_reports_are_persisted_encrypted_and_owner_scoped(client: TestClient) -> None:
    username, token = _create_account(client)
    original_description = (
        "Observed fresh excavation near the river bank; please review this report."
    )
    create = client.post(
        "/reports",
        headers=_headers(token),
        json={
            "location": "Eastern Region, Ghana",
            "description": original_description,
        },
    )
    assert create.status_code == 201, create.text
    report = create.json()
    assert report["reporter"] == username
    assert report["description"] == original_description
    assert report["status"] == "submitted"

    stored, key_version = _stored_description(report["id"])
    assert key_version == 2
    assert original_description not in stored
    decrypted = Fernet(os.environ["REPORT_ENCRYPTION_KEY"].encode("ascii")).decrypt(
        stored.encode("ascii")
    ).decode("utf-8")
    assert decrypted == original_description

    read_back = client.get(f"/reports/{report['id']}", headers=_headers(token))
    assert read_back.status_code == 200
    assert read_back.json()["description"] == original_description

    _other_username, other_token = _create_account(client)
    denied = client.get(f"/reports/{report['id']}", headers=_headers(other_token))
    assert denied.status_code == 404


def test_fake_intelligence_endpoint_is_not_exposed(client: TestClient) -> None:
    # There must be no fabricated "AI alerts" presented as real detections.
    assert client.get("/intel").status_code == 404


def test_evidence_upload_fails_closed_without_private_bucket(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _username, token = _create_account(client)
    monkeypatch.delenv("GLRCHAIN_EVIDENCE_BUCKET", raising=False)
    response = client.post(
        "/evidence",
        headers=_headers(token),
        data={"report_id": "1"},
        files={"file": ("sample.jpg", b"\xff\xd8\xffevidence", "image/jpeg")},
    )
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_database_url_configuration_fails_closed_in_production() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        database_url_from_env({"APP_ENV": "production"})
    assert database_url_from_env({"APP_ENV": "test"}).startswith("sqlite+aiosqlite:///")
    assert normalize_database_url("postgres://user:pass@host/db").startswith("postgresql+asyncpg://")
    assert normalize_database_url("postgresql://user:pass@host/db").startswith("postgresql+asyncpg://")
