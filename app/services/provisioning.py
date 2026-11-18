import httpx
import random
import logging

logger = logging.getLogger(__name__)

class ProvisioningError(Exception):
    """Raised when an external provisioning call fails."""
    pass


async def mock_github_provision(email: str, full_name: str, department: str) -> dict:
    """
    Simulates calling the GitHub API to create an organization member.
    Randomly fails 30% of the time to demonstrate retry logic.
    """
    # Simulate network latency
    import asyncio
    await asyncio.sleep(1.5)
    
    # Simulate random failure
    if random.random() < 0.3:
        raise ProvisioningError(f"GitHub API returned 503 for {email}")
    
    logger.info(f"Successfully provisioned GitHub account for {email}")
    return {
        "system": "github",
        "username": email.split("@")[0],
        "org": "company-org",
        "status": "active"
    }


async def mock_github_deprovision(email: str) -> dict:
    """Simulates removing a user from GitHub org."""
    import asyncio
    await asyncio.sleep(1.0)
    
    if random.random() < 0.3:
        raise ProvisioningError(f"GitHub API returned 503 while removing {email}")
    
    logger.info(f"Successfully deprovisioned GitHub account for {email}")
    return {"system": "github", "status": "removed"}


async def mock_slack_provision(email: str, full_name: str) -> dict:
    """Simulates inviting a user to Slack."""
    import asyncio
    await asyncio.sleep(1.0)
    
    if random.random() < 0.3:
        raise ProvisioningError(f"Slack API returned 429 (rate limit) for {email}")
    
    logger.info(f"Successfully invited {email} to Slack")
    return {"system": "slack", "status": "invited"}