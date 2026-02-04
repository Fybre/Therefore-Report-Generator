"""Dashboard routes."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.auth import get_current_user, require_any_user
from app.store import (
    get_tenants, get_reports, get_users, get_recent_run_logs, get_upcoming_reports
)

router = APIRouter(tags=["dashboard"])


@router.get("/api/stats")
async def get_stats(
    current_user: dict = Depends(require_any_user),
):
    """Get dashboard statistics."""
    tenant_count = len(get_tenants())
    report_count = len(get_reports())
    active_report_count = len([r for r in get_reports() if r.get('enabled', True)])
    user_count = len(get_users())
    
    recent_runs = get_recent_run_logs(10)
    upcoming = get_upcoming_reports(10)
    
    return {
        "total_tenants": tenant_count,
        "total_reports": report_count,
        "active_reports": active_report_count,
        "total_users": user_count,
        "recent_runs": recent_runs,
        "upcoming_runs": upcoming
    }
