from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.database import get_db
from app.models import User, Task, StatusEnum
from app.schemas import DailySummaryResponse, ProductivityHistoryResponse, ProductivitySummaryResponse
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/productivity", tags=["Productivity"])

# ─── Helpers ──────────────────────────────
def get_daily_summary(db: Session, user_id, target_date: date):
    tasks = db.query(Task).filter(
        Task.user_id == user_id,
        Task.date == target_date
    ).all()
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == StatusEnum.COMPLETED)
    percentage = (completed / total * 100) if total > 0 else 0.0
    return {
        "date": target_date,
        "total_tasks": total,
        "completed_tasks": completed,
        "completion_percentage": round(percentage, 2)
    }

# ─── DAILY ─────────────────────────────────
@router.get("/daily/{target_date}", response_model=DailySummaryResponse)
def get_daily(
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = get_daily_summary(db, current_user.id, target_date)
    if result["total_tasks"] == 0:
        raise HTTPException(status_code=404, detail=f"No tasks found for {target_date}")
    return result

# ─── HISTORY ──────────────────────────────
@router.get("/history", response_model=ProductivityHistoryResponse)
def get_history(
    start_date: date = Query(..., description="Start date YYYY-MM-DD"),
    end_date: date = Query(..., description="End date YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    history = []
    current = start_date
    while current <= end_date:
        history.append(get_daily_summary(db, current_user.id, current))
        current += timedelta(days=1)

    return {
        "history": history,
        "period": {"start_date": start_date, "end_date": end_date}
    }

# ─── SUMMARY ──────────────────────────────
@router.get("/summary", response_model=ProductivitySummaryResponse)
def get_summary(
    start_date: date = Query(..., description="Start date YYYY-MM-DD"),
    end_date: date = Query(..., description="End date YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    tasks = db.query(Task).filter(
        Task.user_id == current_user.id,
        Task.date >= start_date,
        Task.date <= end_date
    ).all()

    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == StatusEnum.COMPLETED)
    percentage = (completed / total * 100) if total > 0 else 0.0

    return {
        "period": f"{start_date} to {end_date}",
        "total_tasks": total,
        "completed_tasks": completed,
        "completion_percentage": round(percentage, 2)
    }