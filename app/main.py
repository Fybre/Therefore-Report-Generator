"""FastAPI application."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from app.config import get_settings, BASE_DIR
from app.version import get_version as get_app_version
from app.store import init_store, get_users
from app.scheduler import start_scheduler, stop_scheduler

# Import routers
from app.routers import auth, dashboard, tenants, reports, templates as templates_router, smtp, admin, setup, help as help_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    
    # Initialize data store
    init_store()
    
    # Start scheduler (only if users exist)
    users = get_users()
    if users:
        start_scheduler()
    
    print(f"Starting {settings.APP_NAME}")
    print(f"Debug mode: {settings.DEBUG}")
    if not users:
        print("No users found - setup wizard will be available at /setup")
    
    yield
    
    # Shutdown
    stop_scheduler()
    print(f"Shutting down {settings.APP_NAME}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app_version = get_app_version()
    
    app = FastAPI(
        title=settings.APP_NAME,
        description="Bulk workflow report generator for Therefore",
        version=app_version,
        lifespan=lifespan
    )
    
    # Store version in app state for templates
    app.state.app_version = app_version
    
    # Middleware to inject version into request state for templates
    @app.middleware("http")
    async def version_middleware(request: Request, call_next):
        request.state.app_version = app.state.app_version
        return await call_next(request)
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Static files
    static_dir = BASE_DIR / "app" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # Include routers
    app.include_router(setup.router)  # Setup must be first (no auth required)
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(tenants.router)
    app.include_router(reports.router)
    app.include_router(templates_router.router)
    app.include_router(smtp.router)
    app.include_router(admin.router)
    app.include_router(help_router.router)
    
    # Middleware to redirect to setup if no users exist
    @app.middleware("http")
    async def setup_redirect_middleware(request: Request, call_next):
        # Paths that should not be redirected
        allowed_paths = {'/setup', '/static', '/favicon.ico'}
        
        # Check if path starts with allowed prefix
        path = request.url.path
        if any(path.startswith(p) for p in allowed_paths):
            return await call_next(request)
        
        # Check if users exist
        users = get_users()
        if not users:
            # Redirect to setup
            return RedirectResponse(url="/setup", status_code=302)
        
        return await call_next(request)
    
    # Exception handlers
    @app.exception_handler(404)
    async def not_found_handler(request, exc):
        from fastapi.responses import HTMLResponse
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="templates")
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)
    
    @app.exception_handler(401)
    async def unauthorized_handler(request: Request, exc):
        """Redirect to login on 401."""
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"}
            )
        return RedirectResponse(url="/login", status_code=302)
    
    @app.exception_handler(403)
    async def forbidden_handler(request: Request, exc):
        """Redirect to login on 403."""
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=403,
                content={"detail": "Not authorized"}
            )
        return RedirectResponse(url="/login", status_code=302)
    
    # Redirect root to dashboard or login
    @app.get("/")
    async def root(request: Request):
        from app.auth import get_current_user_from_request
        user = await get_current_user_from_request(request)
        if user:
            return RedirectResponse(url="/dashboard", status_code=302)
        return RedirectResponse(url="/login", status_code=302)
    
    def get_system_alerts():
        """Check for system configuration issues and return alerts."""
        from app.store import get_default_smtp_config, get_tenants
        from app.config import get_settings
        
        alerts = []
        settings = get_settings()
        
        # Check SMTP configuration
        smtp_config = get_default_smtp_config()
        if not smtp_config:
            alerts.append({
                "level": "warning",
                "title": "No SMTP Server Configured",
                "message": "Email reports cannot be sent. Configure SMTP settings.",
                "link": "/smtp",
                "link_text": "Configure SMTP"
            })
        
        # Check if BASE_URL contains localhost (password reset links may not work)
        if 'localhost' in settings.BASE_URL.lower():
            alerts.append({
                "level": "info",
                "title": "Localhost BASE_URL",
                "message": f"BASE_URL contains 'localhost' ({settings.BASE_URL}). Password reset emails may not work correctly from external networks.",
                "link": None,
                "link_text": None
            })
        
        # Check for tenants
        tenants = get_tenants()
        if not tenants:
            alerts.append({
                "level": "warning",
                "title": "No Tenants Configured",
                "message": "Add at least one Therefore tenant to start generating reports.",
                "link": "/tenants/new",
                "link_text": "Add Tenant"
            })
        else:
            # Check for incomplete tenants (missing base_url or auth_token)
            incomplete_tenants = [t for t in tenants if not t.get('base_url') or not t.get('auth_token')]
            if incomplete_tenants:
                alerts.append({
                    "level": "warning",
                    "title": f"{len(incomplete_tenants)} Incomplete Tenant(s)",
                    "message": f"{', '.join(t['name'] for t in incomplete_tenants[:3])}{'...' if len(incomplete_tenants) > 3 else ''} need endpoint and/or auth token configuration.",
                    "link": "/tenants",
                    "link_text": "Configure Tenants"
                })
            
            # Check for inactive tenants
            inactive_tenants = [t for t in tenants if not t.get('is_active', True)]
            if inactive_tenants:
                alerts.append({
                    "level": "info",
                    "title": f"{len(inactive_tenants)} Inactive Tenant(s)",
                    "message": f"{', '.join(t['name'] for t in inactive_tenants[:3])}{'...' if len(inactive_tenants) > 3 else ''} are inactive.",
                    "link": "/tenants",
                    "link_text": "View Tenants"
                })
        
        # Check for users without email (password reset won't work)
        from app.store import get_users
        users = get_users()
        users_without_email = [u for u in users if not u.get('email')]
        if users_without_email and len(users) > 1:  # Don't warn if only admin exists
            alerts.append({
                "level": "info",
                "title": f"{len(users_without_email)} User(s) Without Email",
                "message": "Users without email cannot use password reset feature.",
                "link": "/admin/users",
                "link_text": "Manage Users"
            })
        
        # Check for default admin credentials (security warning)
        # Check if any master_admin user still has default password 'admin'
        import bcrypt
        master_admins = [u for u in users if u.get('role') == 'master_admin']
        for admin_user in master_admins:
            if bcrypt.checkpw('admin'.encode(), admin_user['password_hash'].encode()):
                alerts.append({
                    "level": "danger",
                    "title": "Default Admin Password",
                    "message": f"User '{admin_user.get('username')}' is using default password 'admin'. Change immediately for security.",
                    "link": "/profile",
                    "link_text": "Change Password"
                })
                break  # Only show one alert
        
        return alerts
    
    
    @app.get("/dashboard")
    async def dashboard_redirect(request: Request):
        """Dashboard route that handles auth."""
        from fastapi.templating import Jinja2Templates
        from app.auth import get_current_user_from_request
        from app.store import get_tenants, get_reports, get_users, get_recent_run_logs, get_upcoming_reports, get_report_by_id
        
        templates = Jinja2Templates(directory="templates")
        
        user = await get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        is_master_admin = user.get('role') == 'master_admin'
        
        # Get tenant IDs the user has access to
        if is_master_admin:
            accessible_tenant_ids = {t['id'] for t in get_tenants()}
        else:
            accessible_tenant_ids = {ut.get('tenant_id') for ut in user.get('tenants', [])}
        
        # Get filtered data based on user's access
        all_tenants = get_tenants()
        accessible_tenants = [t for t in all_tenants if t['id'] in accessible_tenant_ids]
        
        all_reports = get_reports()
        accessible_reports = [r for r in all_reports if r.get('tenant_id') in accessible_tenant_ids]
        
        # Get stats (filtered for tenant admins)
        tenant_count = len(accessible_tenants)
        report_count = len(accessible_reports)
        active_report_count = len([r for r in accessible_reports if r.get('enabled', True)])
        user_count = len(get_users()) if is_master_admin else None  # Only show for master admin
        
        # Get recent runs and filter by accessible reports
        all_recent_runs = get_recent_run_logs(50)  # Get more to filter down
        accessible_report_ids = {r['id'] for r in accessible_reports}
        reports_dict = {r['id']: r for r in accessible_reports}
        
        recent_runs = []
        for run in all_recent_runs:
            if run.get('report_id') in accessible_report_ids:
                report = reports_dict.get(run['report_id'])
                run['report_name'] = report['name'] if report else f"Report #{run['report_id']}"
                recent_runs.append(run)
                if len(recent_runs) >= 10:
                    break
        
        # Get upcoming reports (filtered)
        all_upcoming = get_upcoming_reports(50)
        upcoming = [r for r in all_upcoming if r.get('tenant_id') in accessible_tenant_ids][:10]
        
        # Get system alerts
        system_alerts = []
        if is_master_admin:
            # Master admin sees all system alerts
            system_alerts = get_system_alerts()
        else:
            # Tenant admin sees alerts for their assigned tenants
            incomplete_tenants = [t for t in accessible_tenants if not t.get('base_url') or not t.get('auth_token')]
            if incomplete_tenants:
                system_alerts.append({
                    "level": "warning",
                    "title": f"{len(incomplete_tenants)} Incomplete Tenant(s)",
                    "message": f"{', '.join(t['name'] for t in incomplete_tenants[:3])}{'...' if len(incomplete_tenants) > 3 else ''} need endpoint and/or auth token configuration.",
                    "link": "/tenants",
                    "link_text": "Configure Tenants"
                })
            
            # Check for inactive tenants
            inactive_tenants = [t for t in accessible_tenants if not t.get('is_active', True)]
            if inactive_tenants:
                system_alerts.append({
                    "level": "info",
                    "title": f"{len(inactive_tenants)} Inactive Tenant(s)",
                    "message": f"{', '.join(t['name'] for t in inactive_tenants[:3])}{'...' if len(inactive_tenants) > 3 else ''} are inactive.",
                    "link": "/tenants",
                    "link_text": "View Tenants"
                })
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": user,
            "is_master_admin": is_master_admin,
            "stats": {
                "tenants": tenant_count,
                "reports": report_count,
                "active_reports": active_report_count,
                "users": user_count
            },
            "recent_runs": recent_runs,
            "upcoming": upcoming,
            "system_alerts": system_alerts
        })
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
