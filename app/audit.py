"""Transactional, hash-chained application audit events.

This chain is tamper-evident, not immutable. A database administrator capable of
editing all rows and the head can rewrite it; export events to a separately
controlled logging or immutable-retention system for independent trust.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, AuditHead

ZERO_HASH = "0" * 64


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _canonical_payload(
    *,
    event_id: str,
    actor_user_id: int | None,
    action: str,
    object_type: str,
    object_id: str,
    details: dict[str, Any],
    created_at: datetime,
    previous_hash: str,
) -> bytes:
    payload = {
        "event_id": event_id,
        "actor_user_id": actor_user_id,
        "action": action,
        "object_type": object_type,
        "object_id": object_id,
        "details": details,
        "created_at": _utc(created_at).isoformat(timespec="microseconds"),
        "previous_hash": previous_hash,
    }
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def calculate_event_hash(
    *,
    event_id: str,
    actor_user_id: int | None,
    action: str,
    object_type: str,
    object_id: str,
    details: dict[str, Any],
    created_at: datetime,
    previous_hash: str,
) -> str:
    return hashlib.sha256(
        _canonical_payload(
            event_id=event_id,
            actor_user_id=actor_user_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            details=details,
            created_at=created_at,
            previous_hash=previous_hash,
        )
    ).hexdigest()


async def append_audit_event(
    db: AsyncSession,
    *,
    actor_user_id: int | None,
    action: str,
    object_type: str,
    object_id: str,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append an event in the caller's transaction. Caller must commit or roll back."""
    safe_details = details or {}
    # Lock the singleton head so parallel PostgreSQL transactions serialize appends.
    head = await db.scalar(select(AuditHead).where(AuditHead.id == 1).with_for_update())
    if head is None:
        head = AuditHead(id=1, last_hash=ZERO_HASH)
        db.add(head)
        await db.flush()

    event_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    previous_hash = head.last_hash
    event_hash = calculate_event_hash(
        event_id=event_id,
        actor_user_id=actor_user_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        details=safe_details,
        created_at=created_at,
        previous_hash=previous_hash,
    )
    event = AuditEvent(
        event_id=event_id,
        actor_user_id=actor_user_id,
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        details_json=json.dumps(safe_details, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        created_at=created_at,
        previous_hash=previous_hash,
        event_hash=event_hash,
    )
    db.add(event)
    head.last_hash = event_hash
    await db.flush()
    return event


async def verify_audit_chain(db: AsyncSession) -> dict[str, Any]:
    events = (
        await db.scalars(select(AuditEvent).order_by(AuditEvent.sequence.asc()))
    ).all()
    expected_previous = ZERO_HASH

    for event in events:
        try:
            details = json.loads(event.details_json)
            calculated = calculate_event_hash(
                event_id=event.event_id,
                actor_user_id=event.actor_user_id,
                action=event.action,
                object_type=event.object_type,
                object_id=event.object_id,
                details=details,
                created_at=event.created_at,
                previous_hash=expected_previous,
            )
        except (ValueError, TypeError, json.JSONDecodeError):
            return {
                "valid": False,
                "events_checked": event.sequence,
                "first_invalid_sequence": event.sequence,
                "reason": "malformed_event_payload",
            }

        if event.previous_hash != expected_previous or event.event_hash != calculated:
            return {
                "valid": False,
                "events_checked": event.sequence,
                "first_invalid_sequence": event.sequence,
                "reason": "hash_or_link_mismatch",
            }
        expected_previous = event.event_hash

    head = await db.scalar(select(AuditHead).where(AuditHead.id == 1))
    if events and (head is None or head.last_hash != expected_previous):
        return {
            "valid": False,
            "events_checked": len(events),
            "first_invalid_sequence": None,
            "reason": "audit_head_mismatch",
        }
    if not events and head is not None and head.last_hash != ZERO_HASH:
        return {
            "valid": False,
            "events_checked": 0,
            "first_invalid_sequence": None,
            "reason": "nonzero_head_without_events",
        }

    return {
        "valid": True,
        "events_checked": len(events),
        "last_sequence": events[-1].sequence if events else None,
        "last_hash": expected_previous,
    }
