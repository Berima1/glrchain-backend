from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import EvidenceRecord, Report, User
from app.routes.auth import require_roles

router = APIRouter()


@router.get("/stats")
async def stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    reports = await db.scalar(select(func.count()).select_from(Report))
    evidence = await db.scalar(select(func.count()).select_from(EvidenceRecord))
    users = await db.scalar(select(func.count()).select_from(User))
    submitted = await db.scalar(
        select(func.count()).select_from(Report).where(Report.status == "submitted")
    )
    return {
        "reports_total": int(reports or 0),
        "reports_submitted": int(submitted or 0),
        "evidence_records_total": int(evidence or 0),
        "users_total": int(users or 0),
    }
