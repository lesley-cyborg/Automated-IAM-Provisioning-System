from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib, json
from arq.connections import RedisSettings, create_pool

from ..database import get_db
from ..models import User, UserStatus, ProvisioningTask, TaskAction, TaskStatus, IdempotencyKey
from ..schemas import HRWebhookPayload, WebhookResponse
from ..services.audit import log_audit_event
from ..services.security import verify_hmac
from ..logging_config import get_logger

logger = get_logger("webhook")
router = APIRouter()
_redis_pool = None

async def get_redis():
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await create_pool(RedisSettings(host="localhost", port=6379))
    return _redis_pool


@router.post("/api/v1/webhooks/hr-event", response_model=WebhookResponse)
async def handle_hr_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw = await request.body()
    sig = request.headers.get("x-hr-signature")
    if not verify_hmac(raw, sig):
        logger.warning("webhook_signature_invalid")
        raise HTTPException(401, "Invalid HMAC signature")

    payload = HRWebhookPayload(**json.loads(raw))

    payload_hash = hashlib.sha256(raw).hexdigest()
    idem_key = f"hr_event_{payload.email}_{payload_hash[:16]}"
    existing = (await db.execute(
        select(IdempotencyKey).where(IdempotencyKey.key == idem_key)
    )).scalar_one_or_none()
    if existing:
        return WebhookResponse(message="Event already processed",
                               user_id=existing.response_body["user_id"], status="duplicate")

    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if not user:
        user = User(email=payload.email, full_name=payload.full_name,
                    department=payload.department, status=UserStatus.pending)
        db.add(user); await db.flush()
        await log_audit_event(db, "USER_CREATED", "User", user.id,
                              metadata={"email": payload.email, "department": payload.department})

    action = TaskAction.provision if payload.event_type == "user_hired" else TaskAction.deprovision
    tasks = []
    for system in ["mock_github", "mock_slack"]:
        t = ProvisioningTask(user_id=user.id, action=action,
                             target_system=system, status=TaskStatus.pending)
        db.add(t); await db.flush(); tasks.append(t)
        await log_audit_event(db, "PROVISIONING_TASK_CREATED", "ProvisioningTask", t.id,
                              metadata={"user_id": str(user.id), "target_system": system})

    db.add(IdempotencyKey(key=idem_key, request_hash=payload_hash,
                          response_status=202, response_body={"user_id": str(user.id)}))
    await db.commit()

    redis = await get_redis()
    for t in tasks:
        await redis.enqueue_job("provision_user", str(t.id), _queue_name="iam-provisioning")
    logger.info("webhook_accepted", user_id=str(user.id), queued=len(tasks))
    return WebhookResponse(message=f"Accepted. {len(tasks)} tasks queued.",
                           user_id=user.id, status="accepted")