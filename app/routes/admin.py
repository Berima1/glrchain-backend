from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import verify_audit_chain
from app.database import get_db
from app.models import AuditEvent, EvidenceRecord, Report, User
from app.routes.auth import require_roles

router = APIRouter()


@router.get("/stats")
async def stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    reports = await db.scalar(select(func.count()).select_from(Report))
    evidence = await db.scalar(select(func.count()).select_from(EvidenceRecord))
    users = await db.scalar(select(func.count()).select_from(User))
    submitted = await db.scalar(
        select(func.count()).select_from(Report).where(Report.status == "submitted")
    )
    from app.audit import append_audit_event

    await append_audit_event(
        db,
        actor_user_id=current_user.id,
        action="admin.stats_viewed",
        object_type="admin_stats",
        object_id="summary",
        details={},
    )
    await db.commit()
    return {
        "reports_total": int(reports or 0),
        "reports_submitted": int(submitted or 0),
        "evidence_records_total": int(evidence or 0),
        "users_total": int(users or 0),
    }


@router.get("/audit/verify")
async def audit_verify(
    db: AsyncSession = Depends(get_db),
    _auditor: User = Depends(require_roles("admin", "validator")),
):
    """Verify links and hashes for the currently stored application audit chain."""
    result = await verify_audit_chain(db)
    # Verification does not mutate the chain, so its result reflects one read snapshot.
    return result


@router.get("/audit/events")
async def audit_events(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _auditor: User = Depends(require_roles("admin", "validator")),
):
    events = (
        await db.scalars(
            select(AuditEvent)
            .order_by(AuditEvent.sequence.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return {
        "events": [
            {
                "sequence": event.sequence,
                "event_id": event.event_id,
                "actor_user_id": event.actor_user_id,
                "action": event.action,
                "object_type": event.object_type,
                "object_id": event.object_id,
                "details": event.details_json,
                "created_at": event.created_at,
                "previous_hash": event.previous_hash,
                "event_hash": event.event_hash,
            }
            for event in events
        ],
        "limit": limit,
        "offset": offset,
    }
