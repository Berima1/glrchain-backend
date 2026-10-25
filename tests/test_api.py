import hashlib
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


def _set_database_role(username: str, role: str) -> None:
    url = os.environ["DATABASE_URL"]
    if url.startswith("sqlite+aiosqlite:///"):
        path = url.split("sqlite+aiosqlite:///", 1)[1]
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
    else:
        import psycopg2

        sync_url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        with psycopg2.connect(sync_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE users SET role = %s WHERE username = %s", (role, username))


def _tamper_first_audit_event() -> None:
    url = os.environ["DATABASE_URL"]
    if url.startswith("sqlite+aiosqlite:///"):
        path = url.split("sqlite+aiosqlite:///", 1)[1]
        with sqlite3.connect(path) as connection:
            connection.execute(
                "UPDATE audit_events SET details_json = '{\"tampered\":true}' "
                "WHERE sequence = (SELECT MIN(sequence) FROM audit_events)"
            )
    else:
        import psycopg2

        sync_url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        with psycopg2.connect(sync_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE audit_events SET details_json = %s "
                    "WHERE sequence = (SELECT MIN(sequence) FROM audit_events)",
                    ('{"tampered":true}',),
                )


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


def test_private_evidence_upload_and_download_verify_sha256(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routes import reports as reports_routes

    _, token = _create_account(client)
    headers = _headers(token)
    monkeypatch.setenv("GLRCHAIN_EVIDENCE_BUCKET", "glrchain-ci-private-test-bucket")

    report_response = client.post(
        "/reports",
        headers=headers,
        json={
            "location": "Asuogyaman District, Ghana",
            "description": "A sufficiently detailed report to attach evidence during CI testing.",
        },
    )
    assert report_response.status_code == 201, report_response.text
    report_id = report_response.json()["id"]

    evidence_bytes = bytes([0xFF, 0xD8, 0xFF]) + b"glrchain-image-test-bytes"
    captured: dict[str, object] = {}

    def fake_upload(bucket, object_name, data, content_type, metadata):
        captured["bucket"] = bucket
        captured["object_name"] = object_name
        captured["data"] = data
        captured["content_type"] = content_type
        captured["metadata"] = metadata
        return 123

    def fake_download(bucket, object_name):
        assert bucket == "glrchain-ci-private-test-bucket"
        assert object_name == captured["object_name"]
        return evidence_bytes

    monkeypatch.setattr(reports_routes, "_upload_gcs", fake_upload)
    monkeypatch.setattr(reports_routes, "_download_gcs", fake_download)

    uploaded = client.post(
        "/evidence",
        headers=headers,
        data={"report_id": str(report_id)},
        files={"file": ("field-photo.jpg", evidence_bytes, "image/jpeg")},
    )
    assert uploaded.status_code == 201, uploaded.text
    evidence = uploaded.json()
    assert evidence["report_id"] == report_id
    assert evidence["sha256"] == hashlib.sha256(evidence_bytes).hexdigest()
    assert evidence["size_bytes"] == len(evidence_bytes)
    assert captured["content_type"] == "image/jpeg"
    assert captured["metadata"]["sha256"] == evidence["sha256"]

    download = client.get(f"/evidence/{evidence['id']}/content", headers=headers)
    assert download.status_code == 200
    assert download.content == evidence_bytes
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["cache-control"] == "private, no-store"

    _other_user, other_token = _create_account(client)
    denied = client.get(
        f"/evidence/{evidence['id']}/content", headers=_headers(other_token)
    )
    assert denied.status_code == 404


def test_audit_chain_is_verified_and_visible_only_to_privileged_users(client: TestClient) -> None:
    username, token = _create_account(client)
    report_response = client.post(
        "/reports",
        headers=_headers(token),
        json={
            "location": "Asuogyaman District, Ghana",
            "description": "Record this report action in the audit chain for a CI verification.",
        },
    )
    assert report_response.status_code == 201, report_response.text

    assert client.get("/admin/audit/verify", headers=_headers(token)).status_code == 403
    _set_database_role(username, "admin")
    admin_headers = _headers(token)

    verification = client.get("/admin/audit/verify", headers=admin_headers)
    assert verification.status_code == 200, verification.text
    assert verification.json()["valid"] is True
    assert verification.json()["events_checked"] >= 3

    events = client.get("/admin/audit/events", headers=admin_headers)
    assert events.status_code == 200
    actions = [event["action"] for event in events.json()["events"]]
    assert "user.registered" in actions
    assert "auth.login_succeeded" in actions
    assert "report.created" in actions


def test_z_audit_chain_detects_modified_event_data(client: TestClient) -> None:
    username, token = _create_account(client)
    _set_database_role(username, "admin")
    headers = _headers(token)

    before = client.get("/admin/audit/verify", headers=headers)
    assert before.status_code == 200
    assert before.json()["valid"] is True

    _tamper_first_audit_event()
    after = client.get("/admin/audit/verify", headers=headers)
    assert after.status_code == 200
    assert after.json()["valid"] is False
    assert after.json()["reason"] == "hash_or_link_mismatch"
