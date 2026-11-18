import asyncio
from uuid import UUID
from arq.connections import RedisSettings
from sqlalchemy import select

from .database import async_session
from .models import ProvisioningTask, TaskStatus, User
from .services.provisioning import (
    mock_github_provision, mock_github_deprovision,
    mock_slack_provision, ProvisioningError,
)
from .services.audit import log_audit_event
from .logging_config import get_logger

logger = get_logger("worker")
MAX_RETRIES = 3


async def provision_user(ctx: dict, task_id: str):
    task_uuid = UUID(task_id)

    async with async_session() as session:
        task = (await session.execute(
            select(ProvisioningTask).where(ProvisioningTask.id == task_uuid)
        )).scalar_one_or_none()

        if not task or task.status == TaskStatus.completed:
            return

        user = (await session.execute(
            select(User).where(User.id == task.user_id)
        )).scalar_one_or_none()
        if not user:
            task.status = TaskStatus.failed
            task.last_error = "User not found"
            await session.commit()
            return

        try:
            if task.target_system == "mock_github":
                if task.action.value == "provision":
                    await mock_github_provision(user.email, user.full_name, user.department)
                else:
                    await mock_github_deprovision(user.email)
            elif task.target_system == "mock_slack":
                await mock_slack_provision(user.email, user.full_name)
            else:
                raise ProvisioningError(f"Unknown system: {task.target_system}")

            task.status = TaskStatus.completed
            task.last_error = None
            await session.commit()
            await log_audit_event(
                session, "PROVISIONING_COMPLETED", "ProvisioningTask", task.id,
                metadata={"target_system": task.target_system, "action": task.action.value},
            )
            await session.commit()
            logger.info("task_completed", task_id=task_id, system=task.target_system)

        except ProvisioningError as e:
            task.retry_count += 1
            task.last_error = str(e)
            final = task.retry_count >= MAX_RETRIES
            if final:
                task.status = TaskStatus.failed
            await session.commit()

            # FIX: audit EVERY failure, not just terminal ones
            await log_audit_event(
                session, "PROVISIONING_FAILED", "ProvisioningTask", task.id,
                metadata={"error": str(e), "retry_count": task.retry_count, "final": final},
            )
            await session.commit()

            if final:
                logger.error("task_permanently_failed", task_id=task_id,
                             retries=task.retry_count, error=str(e))
            else:
                # FIX: real retry via re-enqueue + exponential backoff (no raise!)
                backoff = 2 ** task.retry_count
                await ctx["redis"].enqueue_job(
                    "provision_user", task_id,
                    _queue_name="iam-provisioning", _defer_by=backoff,
                )
                logger.warning("task_retrying", task_id=task_id,
                               attempt=task.retry_count, defer_by=backoff, error=str(e))


class WorkerSettings:
    functions = [provision_user]
    redis_settings = RedisSettings(host="localhost", port=6379)
    queue_name = "iam-provisioning"
    max_jobs = 30
    job_timeout = 50