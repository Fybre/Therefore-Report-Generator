"""Admin router for user management."""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ..auth import require_master_admin
from ..store import get_users, get_user_by_id, update_user, delete_user, get_tenants, add_audit_log, get_audit_logs

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_class=HTMLResponse)
async def users_admin_page(
    request: Request,
    current_user: dict = Depends(require_master_admin),
):
    """User administration page (master admin only)."""
    templates = Jinja2Templates(directory="templates")
    users_list = get_users()
    tenants_list = get_tenants()
    
    # Enrich user data with tenant names
    tenant_lookup = {t['id']: t for t in tenants_list}
    for user in users_list:
        user_tenants = []
        for ut in user.get('tenants', []):
            tenant = tenant_lookup.get(ut.get('tenant_id'))
            if tenant:
                user_tenants.append({
                    'tenant_id': ut.get('tenant_id'),
                    'tenant_name': tenant['name'],
                    'role': ut.get('role', 'user')
                })
        user['assigned_tenants'] = user_tenants
    
    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "user": current_user,
        "users": users_list,
        "tenants": tenants_list
    })


@router.get("/api/users")
async def list_users(
    current_user: dict = Depends(require_master_admin),
):
    """Get all users (API)."""
    users = get_users()
    # Remove password hashes from response
    for u in users:
        u.pop('password_hash', None)
    return users


@router.get("/api/users/{user_id}")
async def get_user(
    user_id: int,
    current_user: dict = Depends(require_master_admin),
):
    """Get a specific user."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_data = dict(user)
    user_data.pop('password_hash', None)
    user_data['is_self'] = user_id == current_user.get('id')
    return user_data


@router.post("/api/users")
async def create_new_user(
    data: dict,
    current_user: dict = Depends(require_master_admin),
):
    """Create a new user."""
    import bcrypt
    from datetime import datetime
    from ..store import save_yaml, USERS_FILE
    
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'user')
    tenants = data.get('tenants', [])
    
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    if role not in ['user', 'tenant_admin', 'master_admin']:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    # Check if email already exists
    users = get_users()
    for u in users:
        if u.get('email', '').lower() == email.lower():
            raise HTTPException(status_code=400, detail="Email already exists")
    
    # Validate tenants
    if role != 'master_admin' and tenants:
        valid_tenant_ids = {t['id'] for t in get_tenants()}
        for t in tenants:
            if t.get('tenant_id') not in valid_tenant_ids:
                raise HTTPException(status_code=400, detail=f"Invalid tenant_id: {t.get('tenant_id')}")
    
    # Generate ID
    user_id = max([u.get('id', 0) for u in users], default=0) + 1
    
    # Use name as username if provided, otherwise auto-generate from email
    if name:
        username = name
    else:
        username = email.split('@')[0]
        # Ensure uniqueness
        existing_usernames = {u['username'].lower() for u in users}
        base_username = username
        counter = 1
        while username.lower() in existing_usernames:
            username = f"{base_username}{counter}"
            counter += 1
    
    # Create user
    user = {
        'id': user_id,
        'name': name if name else username,
        'username': username,
        'email': email,
        'password_hash': bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        'role': role,
        'is_active': True,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
        'tenants': tenants if role != 'master_admin' else []
    }
    
    users.append(user)
    save_yaml(USERS_FILE, users)
    
    # Audit log
    add_audit_log(
        action='create',
        target_type='user',
        target_id=str(user_id),
        details=f"Created user '{username}' with role '{role}'",
        user_id=current_user.get('id'),
        username=current_user.get('username')
    )
    
    return {"message": f"User '{username}' created successfully", "id": user_id}


@router.put("/api/users/{user_id}")
async def update_existing_user(
    user_id: int,
    data: dict,
    current_user: dict = Depends(require_master_admin),
):
    """Update a user."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    is_self = user_id == current_user.get('id')
    
    updates = {}
    
    # Username (display name) can be updated
    if 'username' in data:
        updates['username'] = data.get('username', '').strip()
    
    # Email cannot be changed via admin (it's the login ID)
    # Role - can't change own role
    if 'role' in data and not is_self:
        role = data['role']
        if role not in ['user', 'tenant_admin', 'master_admin']:
            raise HTTPException(status_code=400, detail="Invalid role")
        updates['role'] = role
    
    # Active status - can't deactivate self
    if 'is_active' in data and not is_self:
        updates['is_active'] = data['is_active']
    
    # Tenants - master admins don't need tenant assignments
    if 'tenants' in data:
        role = data.get('role', user.get('role', 'user'))
        if role != 'master_admin':
            tenants = data['tenants']
            valid_tenant_ids = {t['id'] for t in get_tenants()}
            for t in tenants:
                if t.get('tenant_id') not in valid_tenant_ids:
                    raise HTTPException(status_code=400, detail=f"Invalid tenant_id: {t.get('tenant_id')}")
            updates['tenants'] = tenants
        else:
            updates['tenants'] = []
    
    if updates:
        success = update_user(user_id, updates)
        if success:
            # Build details of what changed
            change_details = []
            if 'email' in updates:
                change_details.append(f"email='{updates['email']}'")
            if 'role' in updates:
                change_details.append(f"role='{updates['role']}'")
            if 'is_active' in updates:
                change_details.append(f"active={updates['is_active']}")
            if 'tenants' in updates:
                tenant_count = len(updates['tenants'])
                change_details.append(f"tenants={tenant_count}")
            
            # Audit log
            add_audit_log(
                action='update',
                target_type='user',
                target_id=str(user_id),
                details=f"Updated user '{user['username']}': {', '.join(change_details)}" if change_details else f"Updated user '{user['username']}'",
                user_id=current_user.get('id'),
                username=current_user.get('username')
            )
            return {"message": f"User '{user['username']}' updated successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update user")
    
    return {"message": "No changes made"}


@router.delete("/api/users/{user_id}")
async def delete_existing_user(
    user_id: int,
    current_user: dict = Depends(require_master_admin),
):
    """Delete a user."""
    if user_id == current_user.get('id'):
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    success = delete_user(user_id)
    if success:
        # Audit log
        add_audit_log(
            action='delete',
            target_type='user',
            target_id=str(user_id),
            details=f"Deleted user '{user['username']}' (role: {user.get('role', 'user')})",
            user_id=current_user.get('id'),
            username=current_user.get('username')
        )
        return {"message": f"User '{user['username']}' deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete user")


@router.post("/api/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: int,
    data: dict,
    current_user: dict = Depends(require_master_admin),
):
    """Reset a user's password."""
    import bcrypt
    
    new_password = data.get('new_password', '')
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    success = update_user(user_id, {'password_hash': new_hash})
    
    if success:
        # Audit log
        add_audit_log(
            action='reset_password',
            target_type='user',
            target_id=str(user_id),
            details=f"Reset password for user '{user['username']}'",
            user_id=current_user.get('id'),
            username=current_user.get('username')
        )
        return {"message": f"Password reset successfully for '{user['username']}'"}
    else:
        raise HTTPException(status_code=500, detail="Failed to reset password")


@router.get("/audit-logs", response_class=HTMLResponse)
async def audit_logs_page(
    request: Request,
    target_type: str = "",
    action: str = "",
    user_id: str = "",
    current_user: dict = Depends(require_master_admin),
):
    """Audit logs view page (master admin only)."""
    templates = Jinja2Templates(directory="templates")
    
    # Parse filters
    target_type_filter = target_type if target_type and target_type.strip() else None
    action_filter = action if action and action.strip() else None
    user_id_int = None
    if user_id and user_id.strip():
        try:
            user_id_int = int(user_id)
        except ValueError:
            pass
    
    # Get audit logs with filters
    logs = get_audit_logs(
        limit=500,
        target_type=target_type_filter,
        action=action_filter,
        user_id=user_id_int
    )
    
    # Get users for filter dropdown
    users_list = get_users()
    
    return templates.TemplateResponse("admin/audit_logs.html", {
        "request": request,
        "user": current_user,
        "logs": logs,
        "users": users_list,
        "filter_target_type": target_type_filter,
        "filter_action": action_filter,
        "filter_user_id": user_id_int
    })


@router.get("/api/audit-logs")
async def get_audit_logs_api(
    target_type: str = None,
    action: str = None,
    user_id: int = None,
    limit: int = 100,
    current_user: dict = Depends(require_master_admin),
):
    """Get audit logs (API) - master admin only."""
    logs = get_audit_logs(
        limit=limit,
        target_type=target_type,
        action=action,
        user_id=user_id
    )
    return logs
