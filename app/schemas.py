from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID
from typing import Optional
from .models import UserStatus, TaskAction, TaskStatus

class HRWebhookPayload(BaseModel):
    event_type: str  # "user_hired" or "user_terminated"
    email: EmailStr
    full_name: str
    department: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    department: str
    status: UserStatus
    created_at: datetime
    
    class Config:
        from_attributes = True

class WebhookResponse(BaseModel):
    message: str
    user_id: UUID
    status: str