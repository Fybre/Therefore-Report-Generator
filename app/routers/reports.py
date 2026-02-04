"""Report management routes."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import (
    get_current_user, 
    require_master_admin, 
    require_admin,
    require_any_user,
    has_tenant_access
)
from app.store import (
    get_reports, get_report_by_id, create_report, update_report, delete_report,
    get_tenants, get_tenant_by_id, get_templates, get_reports_due_now, get_upcoming_reports,
    add_run_log, get_recent_run_logs
)
from app.schemas import ReportCreate, ReportUpdate, RunReportResponse
from app.scheduler import get_scheduler

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/api/reports")
async def list_reports_api(
    tenant_id: int = None,
    current_user: dict = Depends(require_any_user),
):
    """List all reports (API)."""
    reports = get_reports()
    
    if tenant_id:
        if not has_tenant_access(current_user, tenant_id):
            raise HTTPException(status_code=403, detail="Access denied")
        reports = [r for r in reports if r['tenant_id'] == tenant_id]
    elif current_user.get('role') != 'master_admin':
        # Filter to user's tenants
        tenant_ids = [ut.get('tenant_id') for ut in current_user.get('tenants', [])]
        reports = [r for r in reports if r['tenant_id'] in tenant_ids]
    
    return [
        {
            "id": r['id'],
            "name": r['name'],
            "description": r.get('description'),
            "tenant_id": r['tenant_id'],
            "template_id": r['template_id'],
            "workflow_processes": r.get('workflow_processes', []),
            "cron_schedule": r['cron_schedule'],
            "enabled": r.get('enabled', True),
            "next_run": r.get('next_run'),
            "last_run": r.get('last_run'),
            "last_run_status": r.get('last_run_status')
        }
        for r in reports
    ]


@router.get("/api/reports/{report_id}")
async def get_report_api(
    report_id: int,
    current_user: dict = Depends(require_any_user),
):
    """Get report details (API)."""
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not has_tenant_access(current_user, report['tenant_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return report


@router.post("/api/reports")
async def create_report_api(
    report: ReportCreate,
    current_user: dict = Depends(require_any_user),
):
    """Create a new report (API)."""
    if not has_tenant_access(current_user, report.tenant_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if tenant is active
    tenant = get_tenant_by_id(report.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    if not tenant.get('is_active', True):
        raise HTTPException(status_code=400, detail="Cannot create reports for inactive tenants. Please activate the tenant first.")
    
    new_report = create_report(
        name=report.name,
        tenant_id=report.tenant_id,
        template_id=report.template_id,
        cron_schedule=report.cron_schedule,
        description=report.description,
        workflow_processes=report.workflow_processes,
        enabled=report.enabled,
        send_all_to_admin=report.send_all_to_admin,
        admin_email=report.admin_email,
        created_by=current_user['id']
    )
    
    return {
        "id": new_report['id'],
        "name": new_report['name'],
        "message": "Report created successfully"
    }


@router.put("/api/reports/{report_id}")
async def update_report_api(
    report_id: int,
    report_update: ReportUpdate,
    current_user: dict = Depends(require_any_user),
):
    """Update a report (API)."""
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not has_tenant_access(current_user, report['tenant_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    updates = report_update.dict(exclude_unset=True)
    update_report(report_id, updates)
    return {"message": "Report updated successfully"}


@router.delete("/api/reports/{report_id}")
async def delete_report_api(
    report_id: int,
    current_user: dict = Depends(require_any_user),
):
    """Delete a report (API)."""
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not has_tenant_access(current_user, report['tenant_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    delete_report(report_id)
    return {"message": "Report deleted successfully"}


@router.post("/api/reports/{report_id}/run")
async def run_report_api(
    report_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_any_user),
):
    """Run a report manually (API)."""
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not has_tenant_access(current_user, report['tenant_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    scheduler = get_scheduler()
    success, message = await scheduler.run_report_now(report_id)
    
    return {
        "success": success,
        "message": message
    }


# HTML Routes

@router.get("", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Reports list page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    reports = get_reports()
    if current_user.get('role') != 'master_admin':
        tenant_ids = [ut.get('tenant_id') for ut in current_user.get('tenants', [])]
        reports = [r for r in reports if r['tenant_id'] in tenant_ids]
    
    # Get tenants for display
    if current_user.get('role') == 'master_admin':
        tenants = get_tenants()
    else:
        tenant_ids = [ut.get('tenant_id') for ut in current_user.get('tenants', [])]
        tenants = [t for t in get_tenants() if t['id'] in tenant_ids]
    
    # Check for active tenants
    active_tenants = [t for t in tenants if t.get('is_active', True)]
    has_active_tenants = len(active_tenants) > 0
    
    templates_list = get_templates()
    
    return templates.TemplateResponse("reports/list.html", {
        "request": request,
        "user": current_user,
        "reports": reports,
        "tenants": tenants,
        "templates": templates_list,
        "has_active_tenants": has_active_tenants
    })


@router.get("/new", response_class=HTMLResponse)
async def new_report_page(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """New report form."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    # Get active tenants for dropdown
    if current_user.get('role') == 'master_admin':
        tenants = [t for t in get_tenants() if t.get('is_active', True)]
    else:
        tenant_ids = [ut.get('tenant_id') for ut in current_user.get('tenants', [])]
        tenants = [t for t in get_tenants() if t['id'] in tenant_ids and t.get('is_active', True)]
    
    templates_list = get_templates()
    
    return templates.TemplateResponse("reports/form.html", {
        "request": request,
        "user": current_user,
        "report": None,
        "tenants": tenants,
        "templates": templates_list
    })


@router.get("/{report_id}/edit", response_class=HTMLResponse)
async def edit_report_page(
    report_id: int,
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Edit report form."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not has_tenant_access(current_user, report['tenant_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get tenants for dropdown
    if current_user.get('role') == 'master_admin':
        tenants = get_tenants()
    else:
        tenant_ids = [ut.get('tenant_id') for ut in current_user.get('tenants', [])]
        tenants = [t for t in get_tenants() if t['id'] in tenant_ids]
    
    templates_list = get_templates()
    
    return templates.TemplateResponse("reports/form.html", {
        "request": request,
        "user": current_user,
        "report": report,
        "tenants": tenants,
        "templates": templates_list
    })


@router.post("", response_class=HTMLResponse)
async def create_report_form(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Create report from form."""
    form = await request.form()
    
    tenant_id = int(form.get("tenant_id"))
    
    if not has_tenant_access(current_user, tenant_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if tenant is active
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    if not tenant.get('is_active', True):
        raise HTTPException(status_code=400, detail="Cannot create reports for inactive tenants. Please activate the tenant first.")
    
    # Parse workflow processes from JSON (de-duplicate while preserving order)
    processes_json = form.get("workflow_processes_json", "[]")
    processes = []
    if processes_json:
        try:
            import json
            raw_processes = json.loads(processes_json)
            if isinstance(raw_processes, list):
                # De-duplicate while preserving order
                processes = list(dict.fromkeys(raw_processes))
        except:
            processes = []

    create_report(
        name=form.get("name"),
        tenant_id=tenant_id,
        template_id=int(form.get("template_id")),
        cron_schedule=form.get("cron_schedule"),
        description=form.get("description"),
        workflow_processes=processes,
        enabled=form.get("enabled") == "on",
        send_all_to_admin=form.get("send_all_to_admin") == "on",
        admin_email=form.get("admin_email"),
        sort_order=form.get("sort_order", "task_due_date"),
        created_by=current_user['id']
    )
    
    return RedirectResponse(url="/reports", status_code=302)


@router.post("/{report_id}", response_class=HTMLResponse)
async def update_report_form(
    report_id: int,
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Update report from form."""
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not has_tenant_access(current_user, report['tenant_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    form = await request.form()
    
    # Parse workflow processes from JSON (de-duplicate while preserving order)
    processes_json = form.get("workflow_processes_json", "[]")
    processes = []
    if processes_json:
        try:
            import json
            raw_processes = json.loads(processes_json)
            if isinstance(raw_processes, list):
                # De-duplicate while preserving order
                processes = list(dict.fromkeys(raw_processes))
        except:
            processes = []

    updates = {
        'name': form.get("name"),
        'description': form.get("description"),
        'template_id': int(form.get("template_id")),
        'workflow_processes': processes,
        'cron_schedule': form.get("cron_schedule"),
        'enabled': form.get("enabled") == "on",
        'send_all_to_admin': form.get("send_all_to_admin") == "on",
        'admin_email': form.get("admin_email"),
        'sort_order': form.get("sort_order", "task_due_date")
    }
    
    update_report(report_id, updates)
    return RedirectResponse(url="/reports", status_code=302)


@router.post("/{report_id}/delete", response_class=HTMLResponse)
async def delete_report_form(
    report_id: int,
    current_user: dict = Depends(require_any_user),
):
    """Delete report from form."""
    report = get_report_by_id(report_id)
    if report:
        if not has_tenant_access(current_user, report['tenant_id']):
            raise HTTPException(status_code=403, detail="Access denied")
        delete_report(report_id)
    return RedirectResponse(url="/reports", status_code=302)


@router.post("/{report_id}/run", response_class=HTMLResponse)
async def run_report_form(
    report_id: int,
    current_user: dict = Depends(require_any_user),
):
    """Run report from form."""
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not has_tenant_access(current_user, report['tenant_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    scheduler = get_scheduler()
    success, message = await scheduler.run_report_now(report_id)
    
    return RedirectResponse(
        url=f"/reports?message={('Report+run+successfully' if success else 'Report+run+failed')}",
        status_code=302
    )


@router.get("/logs", response_class=HTMLResponse)
async def reports_logs_page(
    request: Request,
    tenant_id: str = "",
    status: str = "",
    date_from: str = "",
    date_to: str = "",
    current_user: dict = Depends(require_any_user),
):
    """Reports run logs page with filtering."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    from app.store import get_run_logs_filtered, get_tenants
    
    # Parse tenant_id from string to int if provided
    tenant_id_int = None
    if tenant_id and tenant_id.strip():
        try:
            tenant_id_int = int(tenant_id)
        except ValueError:
            tenant_id_int = None
    
    # Filter by tenant if specified and user has access
    if tenant_id_int:
        if not has_tenant_access(current_user, tenant_id_int):
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Normalize empty strings to None
    status_filter = status if status and status.strip() else None
    date_from_filter = date_from if date_from and date_from.strip() else None
    date_to_filter = date_to if date_to and date_to.strip() else None
    
    # Get logs with filters
    logs = get_run_logs_filtered(
        tenant_id=tenant_id_int,
        status=status_filter,
        date_from=date_from_filter,
        date_to=date_to_filter,
        limit=500
    )
    
    # Get tenants for filter dropdown
    if current_user.get('role') == 'master_admin':
        tenants = get_tenants()
    else:
        tenant_ids = [ut.get('tenant_id') for ut in current_user.get('tenants', [])]
        tenants = [t for t in get_tenants() if t['id'] in tenant_ids]
    
    return templates.TemplateResponse("reports/logs.html", {
        "request": request,
        "user": current_user,
        "logs": logs,
        "tenants": tenants,
        "filter_tenant_id": tenant_id_int,
        "filter_status": status_filter,
        "filter_date_from": date_from_filter,
        "filter_date_to": date_to_filter
    })


@router.get("/{report_id}/test", response_class=HTMLResponse)
async def test_report_page(
    report_id: int,
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Test report page with preview."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not has_tenant_access(current_user, report['tenant_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get all templates for the dropdown
    templates_list = get_templates()
    
    return templates.TemplateResponse("reports/test.html", {
        "request": request,
        "user": current_user,
        "report": report,
        "templates": templates_list
    })


@router.post("/api/{report_id}/test")
async def test_report_api(
    report_id: int,
    data: dict = None,
    current_user: dict = Depends(require_any_user),
):
    """Test a report without sending emails.
    
    Returns statistics, raw workflow data, and a preview of the first user's email.
    The raw data can be used to re-render with different templates without re-querying.
    """
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not has_tenant_access(current_user, report['tenant_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    from app.services.report import ReportProcessor
    
    # Get optional template_id from request body
    template_id = data.get('template_id') if data else None
    
    processor = ReportProcessor()
    result = await processor.test_report_with_data(report_id, template_id=template_id)
    
    return result


@router.post("/api/{report_id}/render")
async def render_report_preview(
    report_id: int,
    data: dict,
    current_user: dict = Depends(require_any_user),
):
    """Render a preview with provided workflow data and a template.
    
    This allows re-rendering with different templates without re-querying Therefore.
    """
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not has_tenant_access(current_user, report['tenant_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    from app.services.report import ReportProcessor
    
    template_id = data.get('template_id')
    instances_data = data.get('instances_data')
    
    if not instances_data:
        raise HTTPException(status_code=400, detail="No instances_data provided")
    
    processor = ReportProcessor()
    result = processor.render_preview(report, instances_data, template_id)
    
    return result
