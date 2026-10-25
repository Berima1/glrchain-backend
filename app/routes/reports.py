import asyncio
import hashlib
import hmac
import logging
import os
import re
import uuid
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import EvidenceRecord, Report, User
from app.routes.auth import get_current_user
from app.schemas import EvidenceOut, ReportCreate, ReportOut

router = APIRouter()
logger = logging.getLogger("glrchain.reports")
MAX_EVIDENCE_BYTES = 20 * 1024 * 1024
PRIVILEGED_ROLES = {"admin", "validator"}


def _get_report_cipher(version: int = 2) -> Fernet:
    if version == 1:
        # Historical deployments encrypted report descriptions with SECRET_KEY.
        # Set LEGACY_REPORT_ENCRYPTION_KEY explicitly if that historical value differs.
        key = os.getenv("LEGACY_REPORT_ENCRYPTION_KEY") or os.getenv("SECRET_KEY")
        key_label = "legacy report encryption key"
    elif version == 2:
        key = os.getenv("REPORT_ENCRYPTION_KEY")
        key_label = "REPORT_ENCRYPTION_KEY"
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The stored report uses an unsupported encryption-key version.",
        )

    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The {key_label} is not configured; the report was not returned or stored.",
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError):
        logger.error("%s is invalid.", key_label)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The {key_label} is misconfigured; the report was not returned or stored.",
        )


def _report_response(record: Report) -> ReportOut:
    cipher = _get_report_cipher(record.encryption_key_version)
    try:
        description = cipher.decrypt(record.description.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError):
        logger.exception("Unable to decrypt report id=%s; encryption-key integrity may be broken.", record.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The stored report could not be decrypted. Contact the system administrator.",
        )
    return ReportOut(
        id=record.id,
        reporter=record.reporter,
        location=record.location,
        description=description,
        status=record.status,
        created_at=record.created_at,
    )


def _can_access_report(user: User, report: Report) -> bool:
    return user.role in PRIVILEGED_ROLES or report.user_id == user.id


def _safe_filename(filename: str | None) -> str:
    base = Path(filename or "evidence").name
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:255]
    return safe or "evidence"


def _sniff_content_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "video/mp4"
    return None


def _upload_gcs(bucket_name: str, object_name: str, data: bytes, content_type: str, metadata: dict) -> int | None:
    from google.cloud import storage

    client = storage.Client()
    blob = client.bucket(bucket_name).blob(object_name)
    blob.metadata = metadata
    blob.upload_from_string(
        data,
        content_type=content_type,
        if_generation_match=0,
        timeout=60,
    )
    return int(blob.generation) if blob.generation is not None else None


def _download_gcs(bucket_name: str, object_name: str) -> bytes:
    from google.cloud import storage

    return storage.Client().bucket(bucket_name).blob(object_name).download_as_bytes(timeout=60)


def _delete_gcs(bucket_name: str, object_name: str, generation: int | None) -> None:
    from google.cloud import storage

    blob = storage.Client().bucket(bucket_name).blob(object_name)
    blob.delete(if_generation_match=generation, timeout=30)


async def _load_accessible_report(report_id: int, user: User, db: AsyncSession) -> Report:
    report = await db.scalar(select(Report).where(Report.id == report_id))
    if report is None or not _can_access_report(user, report):
        # Use 404 for both non-existent and unauthorised records to avoid leaking IDs.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return report


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cipher = _get_report_cipher(version=2)
    encrypted_description = cipher.encrypt(payload.description.encode("utf-8")).decode("ascii")
    record = Report(
        reporter=current_user.username,
        user_id=current_user.id,
        location=payload.location.strip(),
        description=encrypted_description,
        encryption_key_version=2,
        status="submitted",
    )
    db.add(record)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to persist report.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The report could not be stored. No report receipt was issued.",
        )
    await db.refresh(record)
    return _report_response(record)


@router.get("/reports", response_model=list[ReportOut])
async def list_reports(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Report).order_by(Report.created_at.desc(), Report.id.desc())
    if current_user.role not in PRIVILEGED_ROLES:
        query = query.where(Report.user_id == current_user.id)
    records = (await db.scalars(query.offset(offset).limit(limit))).all()
    return [_report_response(record) for record in records]


@router.get("/reports/{report_id}", response_model=ReportOut)
async def read_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await _load_accessible_report(report_id, current_user, db)
    return _report_response(record)


@router.post("/evidence", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    report_id: int = Form(..., gt=0),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bucket_name = os.getenv("GLRCHAIN_EVIDENCE_BUCKET")
    if not bucket_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private evidence storage is not configured; the file was not accepted.",
        )

    report = await _load_accessible_report(report_id, current_user, db)
    data = await file.read(MAX_EVIDENCE_BYTES + 1)
    await file.close()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The evidence file is empty.")
    if len(data) > MAX_EVIDENCE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Evidence files must be 20 MiB or smaller.")

    detected_type = _sniff_content_type(data)
    if detected_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported evidence type. Accepted types are JPEG, PNG, PDF, and MP4.",
        )

    evidence_id = str(uuid.uuid4())
    digest = hashlib.sha256(data).hexdigest()
    object_name = f"evidence/{report.id}/{evidence_id}"
    safe_name = _safe_filename(file.filename)
    metadata = {
        "sha256": digest,
        "report_id": str(report.id),
        "uploaded_by": str(current_user.id),
    }

    try:
        generation = await asyncio.to_thread(
            _upload_gcs, bucket_name, object_name, data, detected_type, metadata
        )
    except Exception:
        logger.exception("Evidence object upload failed for report id=%s.", report.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private evidence storage is unavailable; no evidence receipt was issued.",
        )

    record = EvidenceRecord(
        id=evidence_id,
        report_id=report.id,
        object_name=object_name,
        sha256=digest,
        size_bytes=len(data),
        content_type=detected_type,
        original_filename=safe_name,
        uploaded_by=current_user.id,
    )
    db.add(record)
    try:
        await db.commit()
        await db.refresh(record)
    except Exception:
        await db.rollback()
        logger.exception("Evidence metadata commit failed; attempting to remove the uploaded object.")
        try:
            await asyncio.to_thread(_delete_gcs, bucket_name, object_name, generation)
        except Exception:
            logger.exception("Cleanup failed for unreferenced evidence object %s.", object_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Evidence metadata could not be committed; no evidence receipt was issued.",
        )
    return record


@router.get("/evidence/{evidence_id}", response_model=EvidenceOut)
async def read_evidence_metadata(
    evidence_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = await db.scalar(select(EvidenceRecord).where(EvidenceRecord.id == evidence_id))
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")
    report = await _load_accessible_report(evidence.report_id, current_user, db)
    return evidence


@router.get("/evidence/{evidence_id}/content")
async def download_evidence(
    evidence_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bucket_name = os.getenv("GLRCHAIN_EVIDENCE_BUCKET")
    if not bucket_name:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Private evidence storage is not configured.")

    evidence = await db.scalar(select(EvidenceRecord).where(EvidenceRecord.id == evidence_id))
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")
    await _load_accessible_report(evidence.report_id, current_user, db)

    try:
        data = await asyncio.to_thread(_download_gcs, bucket_name, evidence.object_name)
    except Exception:
        logger.exception("Failed to retrieve evidence id=%s.", evidence_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Evidence storage is unavailable.")

    actual_digest = hashlib.sha256(data).hexdigest()
    if not hmac.compare_digest(actual_digest, evidence.sha256):
        logger.critical("Evidence integrity check failed for evidence id=%s.", evidence_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Evidence integrity verification failed.")

    # Always send evidence as an attachment; do not render user-supplied content inline.
    return Response(
        content=data,
        media_type=evidence.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="evidence_{evidence.id}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
