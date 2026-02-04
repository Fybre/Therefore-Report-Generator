"""YAML-based data store."""
import os
import yaml
import bcrypt
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import HTTPException

from app.config import DATA_DIR

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# File paths
USERS_FILE = DATA_DIR / "users.yaml"
TENANTS_FILE = DATA_DIR / "tenants.yaml"
REPORTS_FILE = DATA_DIR / "reports.yaml"
TEMPLATES_FILE = DATA_DIR / "templates.yaml"
SMTP_FILE = DATA_DIR / "smtp.yaml"
RUN_LOGS_FILE = DATA_DIR / "run_logs.yaml"
AUDIT_LOG_FILE = DATA_DIR / "audit_log.yaml"
RESET_TOKENS_FILE = DATA_DIR / "reset_tokens.yaml"


def load_yaml(filepath: Path, default: Any = None) -> Any:
    """Load YAML file or return default if not exists."""
    if not filepath.exists():
        return default if default is not None else []
    try:
        with open(filepath, 'r') as f:
            return yaml.safe_load(f) or default
    except Exception:
        return default if default is not None else []


def save_yaml(filepath: Path, data: Any) -> None:
    """Save data to YAML file."""
    with open(filepath, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


# ============== Users ==============

def get_users() -> List[Dict]:
    """Get all users."""
    return load_yaml(USERS_FILE, [])


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID."""
    users = get_users()
    for user in users:
        if user.get('id') == user_id:
            return user
    return None


def get_user_by_username(username: str) -> Optional[Dict]:
    """Get user by username."""
    users = get_users()
    for user in users:
        if user.get('username') == username:
            return user
    return None


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email (case-insensitive)."""
    if not email:
        return None
    users = get_users()
    email_lower = email.lower()
    for user in users:
        if user.get('email', '').lower() == email_lower:
            return user
    return None


def create_user(username: str, password: str, email: str = None, role: str = "user", is_active: bool = True) -> Dict:
    """Create a new user."""
    users = get_users()
    
    # Check if username exists
    if get_user_by_username(username):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email exists (and email is provided)
    if email and get_user_by_email(email):
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Generate ID
    user_id = max([u.get('id', 0) for u in users], default=0) + 1
    
    # Hash password
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    user = {
        'id': user_id,
        'username': username,
        'email': email,
        'password_hash': password_hash,
        'role': role,
        'is_active': is_active,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
        'tenants': []  # List of {tenant_id, role}
    }
    
    users.append(user)
    save_yaml(USERS_FILE, users)
    return user


def update_user(user_id: int, updates: Dict) -> Optional[Dict]:
    """Update a user."""
    users = get_users()
    for i, user in enumerate(users):
        if user.get('id') == user_id:
            # Don't allow changing id
            updates.pop('id', None)
            
            # Hash password if provided
            if 'password' in updates:
                updates['password_hash'] = bcrypt.hashpw(
                    updates.pop('password').encode(), bcrypt.gensalt()
                ).decode()
            
            updates['updated_at'] = datetime.utcnow().isoformat()
            users[i].update(updates)
            save_yaml(USERS_FILE, users)
            return users[i]
    return None


def delete_user(user_id: int) -> bool:
    """Delete a user."""
    users = get_users()
    for i, user in enumerate(users):
        if user.get('id') == user_id:
            users.pop(i)
            save_yaml(USERS_FILE, users)
            return True
    return False


def verify_password(email: str, password: str) -> Optional[Dict]:
    """Verify user password by email."""
    user = get_user_by_email(email)
    if not user:
        return None
    
    if bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
        return user
    return None


# ============== Tenants ==============

def get_tenants() -> List[Dict]:
    """Get all tenants."""
    return load_yaml(TENANTS_FILE, [])


def get_tenant_by_id(tenant_id: int) -> Optional[Dict]:
    """Get tenant by ID."""
    tenants = get_tenants()
    for tenant in tenants:
        if tenant.get('id') == tenant_id:
            return tenant
    return None


def create_tenant(name: str, base_url: str = None, auth_token: str = None, description: str = None, 
                  is_active: bool = True, created_by: int = None) -> Dict:
    """Create a new tenant.
    
    If base_url or auth_token is missing, the tenant will be created as inactive.
    """
    tenants = get_tenants()
    
    tenant_id = max([t.get('id', 0) for t in tenants], default=0) + 1
    
    # If base_url or auth_token is missing, force inactive
    if not base_url or not auth_token:
        is_active = False
    
    tenant = {
        'id': tenant_id,
        'name': name,
        'description': description,
        'base_url': base_url,
        'auth_token': auth_token,
        'is_active': is_active,
        'created_by': created_by,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    tenants.append(tenant)
    save_yaml(TENANTS_FILE, tenants)
    return tenant


def update_tenant(tenant_id: int, updates: Dict) -> Optional[Dict]:
    """Update a tenant."""
    tenants = get_tenants()
    for i, tenant in enumerate(tenants):
        if tenant.get('id') == tenant_id:
            updates.pop('id', None)
            updates['updated_at'] = datetime.utcnow().isoformat()
            tenants[i].update(updates)
            save_yaml(TENANTS_FILE, tenants)
            return tenants[i]
    return None


def delete_tenant(tenant_id: int) -> bool:
    """Delete a tenant and clean up related data (cascade delete)."""
    tenants = get_tenants()
    tenant_found = False
    for i, tenant in enumerate(tenants):
        if tenant.get('id') == tenant_id:
            tenants.pop(i)
            save_yaml(TENANTS_FILE, tenants)
            tenant_found = True
            break
    
    if not tenant_found:
        return False
    
    # Cascade: Remove tenant assignments from users
    users = get_users()
    users_modified = False
    for user in users:
        if 'tenants' in user:
            original_len = len(user['tenants'])
            user['tenants'] = [t for t in user['tenants'] if t.get('tenant_id') != tenant_id]
            if len(user['tenants']) != original_len:
                users_modified = True
                user['updated_at'] = datetime.utcnow().isoformat()
    
    if users_modified:
        save_yaml(USERS_FILE, users)
    
    # Cascade: Delete reports for this tenant
    reports = get_reports()
    original_count = len(reports)
    reports = [r for r in reports if r.get('tenant_id') != tenant_id]
    if len(reports) != original_count:
        save_yaml(REPORTS_FILE, reports)
    
    return True


# ============== Reports ==============

def get_reports() -> List[Dict]:
    """Get all reports."""
    return load_yaml(REPORTS_FILE, [])


def get_report_by_id(report_id: int) -> Optional[Dict]:
    """Get report by ID."""
    reports = get_reports()
    for report in reports:
        if report.get('id') == report_id:
            return report
    return None


def get_reports_for_tenant(tenant_id: int) -> List[Dict]:
    """Get reports for a specific tenant."""
    return [r for r in get_reports() if r.get('tenant_id') == tenant_id]


def create_report(name: str, tenant_id: int, template_id: int, cron_schedule: str,
                  description: str = None, workflow_processes: List[int] = None,
                  enabled: bool = True, send_all_to_admin: bool = False,
                  admin_email: str = None, sort_order: str = "task_due_date",
                  created_by: int = None) -> Dict:
    """Create a new report."""
    reports = get_reports()

    report_id = max([r.get('id', 0) for r in reports], default=0) + 1

    # Calculate next run
    from croniter import croniter
    try:
        itr = croniter(cron_schedule, datetime.now())
        next_run = itr.get_next(datetime).isoformat()
    except:
        next_run = None

    report = {
        'id': report_id,
        'name': name,
        'description': description,
        'tenant_id': tenant_id,
        'template_id': template_id,
        'workflow_processes': workflow_processes or [],
        'cron_schedule': cron_schedule,
        'enabled': enabled,
        'send_all_to_admin': send_all_to_admin,
        'admin_email': admin_email,
        'sort_order': sort_order or "task_due_date",
        'next_run': next_run,
        'last_run': None,
        'last_run_status': None,
        'last_run_message': None,
        'created_by': created_by,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    reports.append(report)
    save_yaml(REPORTS_FILE, reports)
    return report


def update_report(report_id: int, updates: Dict) -> Optional[Dict]:
    """Update a report."""
    reports = get_reports()
    for i, report in enumerate(reports):
        if report.get('id') == report_id:
            updates.pop('id', None)
            
            # Recalculate next_run if cron changed
            if 'cron_schedule' in updates:
                from croniter import croniter
                try:
                    itr = croniter(updates['cron_schedule'], datetime.now())
                    updates['next_run'] = itr.get_next(datetime).isoformat()
                except:
                    updates['next_run'] = None
            
            updates['updated_at'] = datetime.utcnow().isoformat()
            reports[i].update(updates)
            save_yaml(REPORTS_FILE, reports)
            return reports[i]
    return None


def delete_report(report_id: int) -> bool:
    """Delete a report."""
    reports = get_reports()
    for i, report in enumerate(reports):
        if report.get('id') == report_id:
            reports.pop(i)
            save_yaml(REPORTS_FILE, reports)
            return True
    return False


def get_reports_due_now() -> List[Dict]:
    """Get reports that are due to run now."""
    now = datetime.utcnow()
    reports = get_reports()
    due = []
    for report in reports:
        if not report.get('enabled'):
            continue
        next_run = report.get('next_run')
        if next_run:
            next_run_dt = datetime.fromisoformat(next_run) if isinstance(next_run, str) else next_run
            if next_run_dt <= now:
                due.append(report)
    return due


def get_upcoming_reports(limit: int = 10) -> List[Dict]:
    """Get upcoming scheduled reports."""
    now = datetime.utcnow()
    reports = get_reports()
    upcoming = []
    for report in reports:
        if not report.get('enabled'):
            continue
        next_run = report.get('next_run')
        if next_run:
            upcoming.append(report)
    
    # Sort by next_run
    upcoming.sort(key=lambda x: x.get('next_run') or '')
    return upcoming[:limit]


# ============== Email Templates ==============

def get_templates() -> List[Dict]:
    """Get all email templates."""
    return load_yaml(TEMPLATES_FILE, [])


def get_template_by_id(template_id: int) -> Optional[Dict]:
    """Get template by ID."""
    templates = get_templates()
    for template in templates:
        if template.get('id') == template_id:
            return template
    return None


def get_default_template() -> Optional[Dict]:
    """Get the default template."""
    templates = get_templates()
    for template in templates:
        if template.get('is_default'):
            return template
    return templates[0] if templates else None


def create_template(name: str, subject_template: str, body_template: str,
                   description: str = None, is_default: bool = False, 
                   created_by: int = None) -> Dict:
    """Create a new email template."""
    templates = get_templates()
    
    template_id = max([t.get('id', 0) for t in templates], default=0) + 1
    
    # If setting as default, clear others
    if is_default:
        for t in templates:
            t['is_default'] = False
    
    template = {
        'id': template_id,
        'name': name,
        'description': description,
        'subject_template': subject_template,
        'body_template': body_template,
        'is_default': is_default,
        'created_by': created_by,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    templates.append(template)
    save_yaml(TEMPLATES_FILE, templates)
    return template


def update_template(template_id: int, updates: Dict) -> Optional[Dict]:
    """Update a template."""
    templates = get_templates()
    for i, template in enumerate(templates):
        if template.get('id') == template_id:
            updates.pop('id', None)
            
            # If setting as default, clear others
            if updates.get('is_default') and not template.get('is_default'):
                for t in templates:
                    t['is_default'] = False
            
            updates['updated_at'] = datetime.utcnow().isoformat()
            templates[i].update(updates)
            save_yaml(TEMPLATES_FILE, templates)
            return templates[i]
    return None


def delete_template(template_id: int) -> bool:
    """Delete a template."""
    templates = get_templates()
    for i, template in enumerate(templates):
        if template.get('id') == template_id:
            templates.pop(i)
            save_yaml(TEMPLATES_FILE, templates)
            return True
    return False


# ============== SMTP Configs ==============

def get_smtp_configs() -> List[Dict]:
    """Get all SMTP configs."""
    return load_yaml(SMTP_FILE, [])


def get_smtp_config_by_id(config_id: int) -> Optional[Dict]:
    """Get SMTP config by ID."""
    configs = get_smtp_configs()
    for config in configs:
        if config.get('id') == config_id:
            return config
    return None


def get_default_smtp_config() -> Optional[Dict]:
    """Get the default SMTP config."""
    configs = get_smtp_configs()
    for config in configs:
        if config.get('is_default') and config.get('is_active', True):
            return config
    # Return first active if no default
    for config in configs:
        if config.get('is_active', True):
            return config
    return None


def create_smtp_config(name: str, server: str, port: int, username: str, password: str,
                      from_address: str, from_name: str = None, use_tls: bool = True,
                      is_default: bool = False, is_active: bool = True) -> Dict:
    """Create a new SMTP config."""
    configs = get_smtp_configs()
    
    config_id = max([c.get('id', 0) for c in configs], default=0) + 1
    
    # If setting as default, clear others
    if is_default:
        for c in configs:
            c['is_default'] = False
    
    config = {
        'id': config_id,
        'name': name,
        'server': server,
        'port': port,
        'username': username,
        'password': password,
        'use_tls': use_tls,
        'from_address': from_address,
        'from_name': from_name,
        'is_default': is_default,
        'is_active': is_active,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    configs.append(config)
    save_yaml(SMTP_FILE, configs)
    return config


def update_smtp_config(config_id: int, updates: Dict) -> Optional[Dict]:
    """Update an SMTP config."""
    configs = get_smtp_configs()
    for i, config in enumerate(configs):
        if config.get('id') == config_id:
            updates.pop('id', None)
            
            # If setting as default, clear others
            if updates.get('is_default') and not config.get('is_default'):
                for c in configs:
                    c['is_default'] = False
            
            updates['updated_at'] = datetime.utcnow().isoformat()
            configs[i].update(updates)
            save_yaml(SMTP_FILE, configs)
            return configs[i]
    return None


def delete_smtp_config(config_id: int) -> bool:
    """Delete an SMTP config."""
    configs = get_smtp_configs()
    for i, config in enumerate(configs):
        if config.get('id') == config_id:
            configs.pop(i)
            save_yaml(SMTP_FILE, configs)
            return True
    return False


# ============== Run Logs ==============

def get_run_logs() -> List[Dict]:
    """Get all run logs."""
    return load_yaml(RUN_LOGS_FILE, [])


def add_run_log(report_id: int, status: str, message: str = None,
                instances_found: int = 0, emails_sent: int = 0, 
                emails_failed: int = 0) -> Dict:
    """Add a run log entry."""
    logs = get_run_logs()
    
    log_id = max([l.get('id', 0) for l in logs], default=0) + 1
    
    log = {
        'id': log_id,
        'report_id': report_id,
        'started_at': datetime.utcnow().isoformat(),
        'completed_at': datetime.utcnow().isoformat(),
        'status': status,
        'message': message,
        'instances_found': instances_found,
        'emails_sent': emails_sent,
        'emails_failed': emails_failed
    }
    
    logs.append(log)
    save_yaml(RUN_LOGS_FILE, logs)
    return log


def get_recent_run_logs(limit: int = 10) -> List[Dict]:
    """Get recent run logs."""
    logs = get_run_logs()
    # Sort by started_at descending
    logs.sort(key=lambda x: x.get('started_at', ''), reverse=True)
    return logs[:limit]


def get_run_logs_filtered(
    tenant_id: int = None, 
    status: str = None, 
    date_from: str = None,
    date_to: str = None,
    limit: int = 100
) -> List[Dict]:
    """Get run logs with optional filtering.
    
    Args:
        tenant_id: Optional tenant ID to filter by
        status: Optional status to filter by (success, error, partial)
        date_from: Optional start date (ISO format) to filter from
        date_to: Optional end date (ISO format) to filter to
        limit: Maximum number of logs to return
        
    Returns:
        List of run log dictionaries with report_name and tenant_id added
    """
    from datetime import datetime
    
    logs = get_run_logs()
    
    # Get reports to enrich logs with report info
    reports = get_reports()
    reports_dict = {r['id']: r for r in reports}
    
    # Enrich logs with report info
    for log in logs:
        report_id = log.get('report_id')
        report = reports_dict.get(report_id)
        if report:
            log['report_name'] = report.get('name', 'Unknown')
            log['report_tenant_id'] = report.get('tenant_id')
        else:
            log['report_name'] = f"Report #{report_id}"
            log['report_tenant_id'] = None
    
    # Apply filters
    filtered = logs
    
    if tenant_id:
        filtered = [l for l in filtered if l.get('report_tenant_id') == tenant_id]
    
    if status:
        filtered = [l for l in filtered if l.get('status') == status]
    
    # Date range filter
    if date_from or date_to:
        def parse_date(date_str):
            if not date_str:
                return None
            try:
                # Handle ISO format with or without time
                if 'T' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    return datetime.strptime(date_str, '%Y-%m-%d')
            except:
                return None
        
        from_date = parse_date(date_from)
        to_date = parse_date(date_to)
        
        def is_in_date_range(log):
            log_date_str = log.get('started_at', '')
            if not log_date_str:
                return False
            
            try:
                # Parse log date
                if 'T' in log_date_str:
                    log_date = datetime.fromisoformat(log_date_str.replace('Z', '+00:00').replace('+00:00', ''))
                else:
                    log_date = datetime.fromisoformat(log_date_str)
            except:
                return False
            
            # Remove timezone info for comparison
            log_date = log_date.replace(tzinfo=None)
            
            if from_date and log_date < from_date:
                return False
            if to_date:
                # Add one day to include the full end date
                from datetime import timedelta
                end_of_day = to_date + timedelta(days=1)
                if log_date >= end_of_day:
                    return False
            return True
        
        filtered = [l for l in filtered if is_in_date_range(l)]
    
    # Sort by started_at descending
    filtered.sort(key=lambda x: x.get('started_at', ''), reverse=True)
    
    return filtered[:limit]


# ============== Audit Logging ==============

def add_audit_log(action: str, target_type: str, target_id: str = None, 
                  details: str = None, user_id: int = None, username: str = None) -> Dict:
    """Add an audit log entry for administrative actions.
    
    Args:
        action: The action performed (create, update, delete, reset_password, etc.)
        target_type: The type of entity affected (user, tenant, report, template, smtp)
        target_id: Optional ID of the affected entity
        details: Optional details about the action
        user_id: ID of the user who performed the action
        username: Username of the user who performed the action
    
    Returns:
        The created audit log entry
    """
    logs = load_yaml(AUDIT_LOG_FILE, [])
    
    log_id = max([l.get('id', 0) for l in logs], default=0) + 1
    
    log = {
        'id': log_id,
        'timestamp': datetime.utcnow().isoformat(),
        'action': action,
        'target_type': target_type,
        'target_id': target_id,
        'details': details,
        'user_id': user_id,
        'username': username
    }
    
    logs.append(log)
    save_yaml(AUDIT_LOG_FILE, logs)
    return log


def get_audit_logs(limit: int = 100, target_type: str = None, 
                   action: str = None, user_id: int = None) -> List[Dict]:
    """Get audit logs with optional filtering.
    
    Args:
        limit: Maximum number of logs to return
        target_type: Optional filter by target type
        action: Optional filter by action type
        user_id: Optional filter by user who performed the action
    
    Returns:
        List of audit log entries
    """
    logs = load_yaml(AUDIT_LOG_FILE, [])
    
    # Apply filters
    filtered = logs
    
    if target_type:
        filtered = [l for l in filtered if l.get('target_type') == target_type]
    
    if action:
        filtered = [l for l in filtered if l.get('action') == action]
    
    if user_id:
        filtered = [l for l in filtered if l.get('user_id') == user_id]
    
    # Sort by timestamp descending (most recent first)
    filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return filtered[:limit]


# ============== Initialization ==============

def init_store():
    """Initialize the data store - ensures data directory exists.
    
    Note: Admin user creation is now handled by the setup wizard at /setup
    """
    # Data directory is created at module import time via DATA_DIR.mkdir()
    # No automatic admin creation - user must run setup wizard
    pass


# ============== Password Reset Tokens ==============

def create_password_reset_token(user_id: int, token: str, expires_at: datetime) -> Dict:
    """Create a password reset token for a user.
    
    Args:
        user_id: The user ID
        token: The secure random token
        expires_at: Token expiration datetime
    
    Returns:
        The created token record
    """
    tokens = load_yaml(RESET_TOKENS_FILE, [])
    
    # Remove any existing tokens for this user
    tokens = [t for t in tokens if t.get('user_id') != user_id]
    
    token_record = {
        'id': max([t.get('id', 0) for t in tokens], default=0) + 1,
        'user_id': user_id,
        'token': token,
        'created_at': datetime.utcnow().isoformat(),
        'expires_at': expires_at.isoformat(),
        'used': False
    }
    
    tokens.append(token_record)
    save_yaml(RESET_TOKENS_FILE, tokens)
    return token_record


def get_password_reset_token(token: str) -> Optional[Dict]:
    """Get a password reset token by token string.
    
    Args:
        token: The token string
    
    Returns:
        The token record if found and valid, None otherwise
    """
    tokens = load_yaml(RESET_TOKENS_FILE, [])
    for t in tokens:
        if t.get('token') == token and not t.get('used', False):
            # Check expiration
            expires_at = t.get('expires_at')
            if expires_at:
                try:
                    expires = datetime.fromisoformat(expires_at)
                    if expires > datetime.utcnow():
                        return t
                except:
                    pass
    return None


def mark_token_used(token: str) -> bool:
    """Mark a password reset token as used.
    
    Args:
        token: The token string
    
    Returns:
        True if token was found and marked used, False otherwise
    """
    tokens = load_yaml(RESET_TOKENS_FILE, [])
    for t in tokens:
        if t.get('token') == token:
            t['used'] = True
            t['used_at'] = datetime.utcnow().isoformat()
            save_yaml(RESET_TOKENS_FILE, tokens)
            return True
    return False


def cleanup_expired_tokens():
    """Remove expired and used tokens (called periodically)."""
    tokens = load_yaml(RESET_TOKENS_FILE, [])
    now = datetime.utcnow()
    
    valid_tokens = []
    for t in tokens:
        # Keep if not used and not expired
        if t.get('used', False):
            continue
        
        expires_at = t.get('expires_at')
        if expires_at:
            try:
                expires = datetime.fromisoformat(expires_at)
                if expires > now:
                    valid_tokens.append(t)
            except:
                pass
    
    if len(valid_tokens) != len(tokens):
        save_yaml(RESET_TOKENS_FILE, valid_tokens)
