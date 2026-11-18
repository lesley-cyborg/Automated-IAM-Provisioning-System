from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from arq.connections import RedisSettings, create_pool
from uuid import UUID

from ..database import get_db
from ..models import AuditLog, ProvisioningTask, TaskStatus
from ..services.security import require_role
from ..schemas import UserResponse

router = APIRouter()
_redis = None
async def get_redis():
    global _redis
    if _redis is None:
        _redis = await create_pool(RedisSettings(host="localhost", port=6379))
    return _redis

@router.get("/api/v1/audit-logs")
async def list_audit_logs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    rows = (await db.execute(
        select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit)
    )).scalars().all()
    return [{"action": r.action, "resource_type": r.resource_type,
             "resource_id": str(r.resource_id), "metadata": r.event_metadata,
             "timestamp": r.timestamp} for r in rows]

@router.post("/api/v1/tasks/{task_id}/retry")
async def retry_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Manual retry — also the backfill for orphaned Week-1 tasks (jane.doe)."""
    task = (await db.execute(
        select(ProvisioningTask).where(ProvisioningTask.id == task_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    task.status = TaskStatus.pending
    task.retry_count = 0
    await db.commit()
    redis = await get_redis()
    await redis.enqueue_job("provision_user", str(task_id), _queue_name="iam-provisioning")
    return {"message": "re-enqueued", "task_id": str(task_id)}