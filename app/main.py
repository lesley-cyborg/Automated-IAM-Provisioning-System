from fastapi import FastAPI
from contextlib import asynccontextmanager
from .database import engine, Base
from .routers import webhooks, auth, audit
from .logging_config import setup_logging

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="IAM Provisioning Service", version="0.2.0", lifespan=lifespan)
app.include_router(webhooks.router)
app.include_router(auth.router)
app.include_router(audit.router)

@app.get("/health")
async def health(): return {"status": "healthy"}