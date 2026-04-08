from fastapi import APIRouter, Depends, Query
from console.backend.auth import require_editor_or_admin
from console.backend.services.system_service import SystemService

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def get_health(_user=Depends(require_editor_or_admin)):
    return SystemService().get_health()


@router.get("/cron")
def get_cron(_user=Depends(require_editor_or_admin)):
    return SystemService().get_cron()


@router.get("/errors")
def get_errors(
    limit: int = Query(50, ge=1, le=200),
    _user=Depends(require_editor_or_admin),
):
    return SystemService().get_errors(limit)
