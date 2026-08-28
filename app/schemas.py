from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime, date
from typing import Optional, List
from enum import Enum

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Status(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"

# ─── AUTH SCHEMAS ───────────────────────────
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class OTPVerify(BaseModel):
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6)

class OTPRequest(BaseModel):
    email: EmailStr

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    is_verified: bool
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# ─── TASK SCHEMAS ───────────────────────────
class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    date: date
    priority: Priority = Priority.MEDIUM

class UpdateTaskRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    date: Optional[date] = None
    priority: Optional[Priority] = None
    status: Optional[Status] = None

class TaskResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: Optional[str]
    date: date
    priority: Priority
    status: Status
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int

class TaskListResponse(BaseModel):
    items: List[TaskResponse]
    pagination: PaginationMeta

# ─── PRODUCTIVITY SCHEMAS ───────────────────
class DailySummaryResponse(BaseModel):
    date: date
    total_tasks: int
    completed_tasks: int
    completion_percentage: float

class ProductivityHistoryResponse(BaseModel):
    history: List[DailySummaryResponse]
    period: dict

class ProductivitySummaryResponse(BaseModel):
    period: str
    total_tasks: int
    completed_tasks: int
    completion_percentage: float