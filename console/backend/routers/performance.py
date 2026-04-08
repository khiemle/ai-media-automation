from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.performance_service import PerformanceService

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/summary")
def get_summary(db: Session = Depends(get_db), _user=Depends(require_editor_or_admin)):
    return PerformanceService(db).get_summary()


@router.get("/daily")
def get_daily(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return PerformanceService(db).get_daily(days)


@router.get("/niches")
def get_niches(db: Session = Depends(get_db), _user=Depends(require_editor_or_admin)):
    return PerformanceService(db).get_niches()


@router.get("/top-videos")
def get_top_videos(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return PerformanceService(db).get_top_videos(limit)
