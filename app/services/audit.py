from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
import json

from ..models import AuditLog

async def log_audit_event(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: UUID,
    actor_id: Optional[UUID] = None,
    metadata: Optional[dict] = None
):
    audit_log = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        event_metadata=metadata
    )
    db.add(audit_log)
    await db.flush()