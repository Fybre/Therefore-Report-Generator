"""Help documentation routes."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from app.auth import get_current_user, require_any_user

router = APIRouter(prefix="/help", tags=["help"])


@router.get("", response_class=HTMLResponse)
async def help_index(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Help index page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("help/index.html", {
        "request": request,
        "user": current_user,
        "title": "Help & Documentation",
        "section": "index"
    })


@router.get("/getting-started", response_class=HTMLResponse)
async def help_getting_started(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Getting started guide."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("help/getting-started.html", {
        "request": request,
        "user": current_user,
        "title": "Getting Started",
        "section": "getting-started"
    })


@router.get("/tenants", response_class=HTMLResponse)
async def help_tenants(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Tenants help page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("help/tenants.html", {
        "request": request,
        "user": current_user,
        "title": "Tenants",
        "section": "tenants"
    })


@router.get("/reports", response_class=HTMLResponse)
async def help_reports(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Reports help page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("help/reports.html", {
        "request": request,
        "user": current_user,
        "title": "Reports",
        "section": "reports"
    })


@router.get("/templates", response_class=HTMLResponse)
async def help_templates(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Email templates help page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("help/templates.html", {
        "request": request,
        "user": current_user,
        "title": "Email Templates",
        "section": "templates"
    })


@router.get("/smtp", response_class=HTMLResponse)
async def help_smtp(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """SMTP settings help page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("help/smtp.html", {
        "request": request,
        "user": current_user,
        "title": "SMTP Settings",
        "section": "smtp"
    })


@router.get("/users", response_class=HTMLResponse)
async def help_users(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """User management help page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("help/users.html", {
        "request": request,
        "user": current_user,
        "title": "User Management",
        "section": "users"
    })


@router.get("/roles", response_class=HTMLResponse)
async def help_roles(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """User roles help page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("help/roles.html", {
        "request": request,
        "user": current_user,
        "title": "User Roles & Permissions",
        "section": "roles"
    })


@router.get("/troubleshooting", response_class=HTMLResponse)
async def help_troubleshooting(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Troubleshooting help page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("help/troubleshooting.html", {
        "request": request,
        "user": current_user,
        "title": "Troubleshooting",
        "section": "troubleshooting"
    })
