from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import date
from typing import Optional

from app.database import get_db
from app.models import User, Task, PriorityEnum, StatusEnum
from app.schemas import (
    CreateTaskRequest, UpdateTaskRequest, TaskResponse,
    TaskListResponse, PaginationMeta
)
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])

# ─── Helpers ──────────────────────────────
def get_task_or_404(task_id: UUID, user_id: UUID, db: Session) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# ─── CREATE ────────────────────────────────
@router.post("/", response_model=TaskResponse, status_code=201)
def create_task(
    task_data: CreateTaskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = Task(
        user_id=current_user.id,
        title=task_data.title,
        description=task_data.description,
        date=task_data.date,
        priority=task_data.priority
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

# ─── LIST WITH FILTERS, PAGINATION, SORT ──
@router.get("/", response_model=TaskListResponse)
def list_tasks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    date_filter: Optional[date] = Query(None, alias="date"),
    status: Optional[StatusEnum] = None,
    priority: Optional[PriorityEnum] = None,
    sort: str = Query("created_at", regex="^(created_at|updated_at|date|priority)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Task).filter(Task.user_id == current_user.id)

    if date_filter:
        query = query.filter(Task.date == date_filter)
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)

    total = query.count()

    sort_column = getattr(Task, sort, Task.created_at)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    tasks = query.offset((page - 1) * limit).limit(limit).all()

    total_pages = (total + limit - 1) // limit

    return {
        "items": tasks,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages
        }
    }

# ─── GET ONE ──────────────────────────────
@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_task_or_404(task_id, current_user.id, db)

# ─── UPDATE ───────────────────────────────
@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: UUID,
    task_data: UpdateTaskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = get_task_or_404(task_id, current_user.id, db)

    # Handle status change to set completed_at
    if task_data.status == StatusEnum.COMPLETED and task.status != StatusEnum.COMPLETED:
        task.completed_at = datetime.utcnow()
    elif task_data.status == StatusEnum.PENDING:
        task.completed_at = None

    update_data = task_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task

# ─── DELETE ───────────────────────────────
@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = get_task_or_404(task_id, current_user.id, db)
    db.delete(task)
    db.commit()