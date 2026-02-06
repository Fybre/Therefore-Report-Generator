"""Tenant management routes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import (
    get_current_user, 
    require_master_admin, 
    require_admin,
    require_any_user,
    has_tenant_access,
    is_tenant_admin
)
from app.store import (
    get_tenants, get_tenant_by_id, create_tenant, update_tenant, delete_tenant,
    get_reports_for_tenant, add_audit_log
)
from app.schemas import TenantCreate, TenantUpdate
from app.services.therefore import ThereforeClient

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/api/tenants")
async def list_tenants_api(
    current_user: dict = Depends(require_any_user),
):
    """List all tenants (API)."""
    if current_user.get('role') == 'master_admin':
        tenants = get_tenants()
    else:
        # Only show tenants user has access to
        tenant_ids = [ut.get('tenant_id') for ut in current_user.get('tenants', [])]
        tenants = [t for t in get_tenants() if t['id'] in tenant_ids]
    
    return [
        {
            "id": t['id'],
            "name": t['name'],
            "description": t.get('description'),
            "base_url": t['base_url'],
            "is_active": t.get('is_active', True),
            "created_at": t.get('created_at')
        }
        for t in tenants
    ]


@router.get("/api/tenants/{tenant_id}")
async def get_tenant_api(
    tenant_id: int,
    current_user: dict = Depends(require_any_user),
):
    """Get tenant details (API)."""
    if not has_tenant_access(current_user, tenant_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Get report count
    report_count = len(get_reports_for_tenant(tenant_id))
    
    return {
        "id": tenant['id'],
        "name": tenant['name'],
        "description": tenant.get('description'),
        "base_url": tenant['base_url'],
        "is_active": tenant.get('is_active', True),
        "created_at": tenant.get('created_at'),
        "report_count": report_count
    }


@router.post("/api/tenants")
async def create_tenant_api(
    tenant: TenantCreate,
    current_user: dict = Depends(require_master_admin),
):
    """Create a new tenant (API)."""
    new_tenant = create_tenant(
        name=tenant.name,
        description=tenant.description,
        base_url=tenant.base_url,
        auth_token=tenant.auth_token,
        is_active=tenant.is_active,
        is_single_instance=tenant.is_single_instance,
        created_by=current_user['id']
    )
    
    # Audit log
    add_audit_log(
        action='create',
        target_type='tenant',
        target_id=str(new_tenant['id']),
        details=f"Created tenant '{new_tenant['name']}'",
        user_id=current_user.get('id'),
        username=current_user.get('username')
    )
    
    return {
        "id": new_tenant['id'],
        "name": new_tenant['name'],
        "message": "Tenant created successfully"
    }


@router.put("/api/tenants/{tenant_id}")
async def update_tenant_api(
    tenant_id: int,
    tenant_update: TenantUpdate,
    current_user: dict = Depends(require_any_user),
):
    """Update a tenant (API)."""
    if current_user.get('role') != 'master_admin' and not is_tenant_admin(current_user, tenant_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    updates = tenant_update.dict(exclude_unset=True)
    if 'auth_token' in updates and not updates['auth_token']:
        updates.pop('auth_token')  # Keep existing if empty
    
    # Check if trying to activate an incomplete tenant
    if updates.get('is_active', False):
        # Check base_url
        base_url = updates.get('base_url') or tenant.get('base_url')
        # Check auth_token (from updates or existing tenant)
        auth_token = updates.get('auth_token') if updates.get('auth_token') else tenant.get('auth_token')
        
        if not base_url or not auth_token:
            raise HTTPException(
                status_code=400,
                detail="Cannot activate tenant: Base URL and Authorization Token are required."
            )
    
    update_tenant(tenant_id, updates)
    
    # Audit log
    change_details = [f"{k}='{v}'" for k, v in updates.items() if k != 'auth_token']
    add_audit_log(
        action='update',
        target_type='tenant',
        target_id=str(tenant_id),
        details=f"Updated tenant '{tenant['name']}': {', '.join(change_details)}" if change_details else f"Updated tenant '{tenant['name']}'",
        user_id=current_user.get('id'),
        username=current_user.get('username')
    )
    
    return {"message": "Tenant updated successfully"}


@router.delete("/api/tenants/{tenant_id}")
async def delete_tenant_api(
    tenant_id: int,
    current_user: dict = Depends(require_master_admin),
):
    """Delete a tenant (API)."""
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    tenant_name = tenant['name']
    if delete_tenant(tenant_id):
        # Audit log
        add_audit_log(
            action='delete',
            target_type='tenant',
            target_id=str(tenant_id),
            details=f"Deleted tenant '{tenant_name}' (cascade: removed user assignments and reports)",
            user_id=current_user.get('id'),
            username=current_user.get('username')
        )
        return {"message": "Tenant deleted successfully"}
    raise HTTPException(status_code=404, detail="Tenant not found")


# HTML Routes

@router.get("", response_class=HTMLResponse)
async def tenants_page(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Tenants list page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    if current_user.get('role') == 'master_admin':
        tenants_list = get_tenants()
    else:
        tenant_ids = [ut.get('tenant_id') for ut in current_user.get('tenants', [])]
        tenants_list = [t for t in get_tenants() if t['id'] in tenant_ids]
    
    return templates.TemplateResponse("tenants/list.html", {
        "request": request,
        "user": current_user,
        "tenants": tenants_list
    })


@router.get("/new", response_class=HTMLResponse)
async def new_tenant_page(
    request: Request,
    current_user: dict = Depends(require_master_admin)
):
    """New tenant form."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("tenants/form.html", {
        "request": request,
        "user": current_user,
        "tenant": None
    })


@router.get("/{tenant_id}/edit", response_class=HTMLResponse)
async def edit_tenant_page(
    tenant_id: int,
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Edit tenant form."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    if not has_tenant_access(current_user, tenant_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return templates.TemplateResponse("tenants/form.html", {
        "request": request,
        "user": current_user,
        "tenant": tenant
    })


@router.post("", response_class=HTMLResponse)
async def create_tenant_form(
    request: Request,
    current_user: dict = Depends(require_master_admin),
):
    """Create tenant from form."""
    form = await request.form()
    
    create_tenant(
        name=form.get("name"),
        description=form.get("description"),
        base_url=form.get("base_url"),
        auth_token=form.get("auth_token"),
        is_active=form.get("is_active") == "on",
        is_single_instance=form.get("is_single_instance") == "on",
        created_by=current_user['id']
    )
    
    return RedirectResponse(url="/tenants", status_code=302)


@router.post("/{tenant_id}", response_class=HTMLResponse)
async def update_tenant_form(
    tenant_id: int,
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Update tenant from form."""
    if current_user.get('role') != 'master_admin' and not is_tenant_admin(current_user, tenant_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    form = await request.form()
    
    is_active = form.get("is_active") == "on"
    is_single_instance = form.get("is_single_instance") == "on"
    base_url = form.get("base_url")
    auth_token = form.get("auth_token")
    
    # Check if trying to activate an incomplete tenant
    if is_active:
        # Use existing values if not provided in form
        final_base_url = base_url if base_url else tenant.get('base_url')
        final_auth_token = auth_token if auth_token else tenant.get('auth_token')
        
        if not final_base_url or not final_auth_token:
            # Return to form with error
            from fastapi.templating import Jinja2Templates
            templates = Jinja2Templates(directory="templates")
            
            # Reconstruct tenant with form values for display
            display_tenant = {
                'id': tenant_id,
                'name': form.get("name"),
                'description': form.get("description"),
                'base_url': base_url,
                'auth_token': auth_token,
                'is_active': is_active,
                'is_single_instance': is_single_instance
            }
            
            return templates.TemplateResponse("tenants/form.html", {
                "request": request,
                "user": current_user,
                "tenant": display_tenant,
                "error": "Cannot activate tenant: Base URL and Authorization Token are required."
            })
    
    updates = {
        'name': form.get("name"),
        'description': form.get("description"),
        'base_url': base_url,
        'is_active': is_active,
        'is_single_instance': is_single_instance
    }
    
    if auth_token:
        updates['auth_token'] = auth_token
    
    update_tenant(tenant_id, updates)
    return RedirectResponse(url="/tenants", status_code=302)


@router.post("/{tenant_id}/delete", response_class=HTMLResponse)
async def delete_tenant_form(
    tenant_id: int,
    current_user: dict = Depends(require_master_admin),
):
    """Delete tenant from form."""
    delete_tenant(tenant_id)
    return RedirectResponse(url="/tenants", status_code=302)


# Test connection endpoints

@router.post("/api/{tenant_id}/test")
async def test_existing_tenant_connection(
    tenant_id: int,
    current_user: dict = Depends(require_any_user),
):
    """Test connection to an existing saved tenant using stored credentials."""
    if not has_tenant_access(current_user, tenant_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    client = ThereforeClient(
        base_url=tenant['base_url'],
        tenant_name=tenant['name'],
        auth_token=tenant['auth_token'],
        is_single_instance=tenant.get('is_single_instance', False)
    )
    
    try:
        result = await client.test_connection()
        return result
    finally:
        await client.close()


@router.post("/api/test")
async def test_new_tenant_connection(
    data: dict,
    current_user: dict = Depends(require_master_admin),
):
    """Test connection with provided credentials (for new tenants before saving)."""
    base_url = data.get('base_url')
    tenant_name = data.get('tenant_name') or data.get('name')
    auth_token = data.get('auth_token')
    is_single_instance = data.get('is_single_instance', False)
    
    if not base_url or not tenant_name or not auth_token:
        raise HTTPException(
            status_code=400, 
            detail="Missing required fields: base_url, tenant_name (or name), auth_token"
        )
    
    client = ThereforeClient(
        base_url=base_url,
        tenant_name=tenant_name,
        auth_token=auth_token,
        is_single_instance=is_single_instance
    )
    
    try:
        result = await client.test_connection()
        return result
    finally:
        await client.close()


@router.get("/api/{tenant_id}/processes")
async def get_tenant_workflow_processes(
    tenant_id: int,
    refresh: bool = False,
    current_user: dict = Depends(require_any_user),
):
    """Get all workflow processes for a tenant.
    
    This queries all workflow instances and extracts unique process information.
    Results are cached for 1 hour. Use refresh=true to bypass cache.
    """
    if not has_tenant_access(current_user, tenant_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    client = ThereforeClient(
        base_url=tenant['base_url'],
        tenant_name=tenant['name'],
        auth_token=tenant['auth_token'],
        is_single_instance=tenant.get('is_single_instance', False)
    )
    
    try:
        processes = await client.get_all_workflow_processes(use_cache=not refresh)
        return {
            "success": True,
            "processes": processes,
            "cached": not refresh
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "processes": [],
            "cached": False
        }
    finally:
        await client.close()
