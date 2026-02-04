"""Setup wizard for initial configuration."""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import bcrypt
from datetime import datetime

from app.store import get_users, save_yaml, USERS_FILE
from app.config import DATA_DIR

router = APIRouter(tags=["setup"])

# File to store app configuration (BASE_URL, etc.)
APP_CONFIG_FILE = DATA_DIR / "app_config.yaml"


def get_app_config() -> dict:
    """Get application configuration from file."""
    if not APP_CONFIG_FILE.exists():
        return {}
    try:
        import yaml
        with open(APP_CONFIG_FILE, 'r') as f:
            return yaml.safe_load(f) or {}
    except:
        return {}


def save_app_config(config: dict):
    """Save application configuration to file."""
    import yaml
    with open(APP_CONFIG_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)


def get_base_url_from_request(request: Request) -> str:
    """Extract base URL from the incoming request."""
    scheme = request.url.scheme
    host = request.headers.get('host', request.url.hostname)
    return f"{scheme}://{host}"


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Initial setup page - only shown when no users exist."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    # If users already exist, redirect to login
    users = get_users()
    if users:
        return RedirectResponse(url="/login", status_code=302)
    
    # Auto-detect base URL
    detected_base_url = get_base_url_from_request(request)
    
    return templates.TemplateResponse("setup.html", {
        "request": request,
        "detected_base_url": detected_base_url
    })


@router.post("/setup")
async def setup_submit(request: Request):
    """Process initial setup form."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    # If users already exist, redirect to login
    users = get_users()
    if users:
        return RedirectResponse(url="/login", status_code=302)
    
    form = await request.form()
    
    admin_name = form.get("admin_name", "").strip()
    admin_email = form.get("admin_email", "").strip()
    admin_password = form.get("admin_password", "")
    confirm_password = form.get("confirm_password", "")
    base_url = form.get("base_url", "").strip()
    
    errors = []
    
    # Validate name
    if not admin_name:
        errors.append("Full name is required")
    
    # Validate email
    if not admin_email or "@" not in admin_email:
        errors.append("A valid email address is required")
    
    # Validate password
    if not admin_password or len(admin_password) < 6:
        errors.append("Password must be at least 6 characters")
    
    if admin_password != confirm_password:
        errors.append("Passwords do not match")
    
    # Validate base URL
    if not base_url:
        errors.append("Base URL is required")
    elif not (base_url.startswith("http://") or base_url.startswith("https://")):
        errors.append("Base URL must start with http:// or https://")
    
    if errors:
        return templates.TemplateResponse("setup.html", {
            "request": request,
            "detected_base_url": base_url or get_base_url_from_request(request),
            "errors": errors,
            "admin_name": admin_name,
            "admin_email": admin_email
        })
    
    # Create admin user
    admin = {
        'id': 1,
        'name': admin_name,
        'username': admin_name,  # Use full name as username/display name
        'email': admin_email,
        'password_hash': bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode(),
        'role': 'master_admin',
        'is_active': True,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
        'tenants': []
    }
    
    save_yaml(USERS_FILE, [admin])
    
    # Save app configuration
    config = {
        'base_url': base_url.rstrip('/'),
        'setup_completed': True,
        'setup_at': datetime.utcnow().isoformat()
    }
    save_app_config(config)
    
    print(f"[SETUP] Created admin user: {admin_email}")
    print(f"[SETUP] Base URL configured: {base_url}")
    
    # Redirect to login with success message
    return RedirectResponse(
        url="/login?message=Setup+completed+successfully.+Please+log+in.",
        status_code=302
    )


def is_setup_complete() -> bool:
    """Check if initial setup has been completed."""
    return len(get_users()) > 0
