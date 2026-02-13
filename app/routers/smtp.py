"""SMTP configuration routes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.auth import require_master_admin, require_any_user
from app.store import (
    get_smtp_configs, get_smtp_config_by_id, create_smtp_config, 
    update_smtp_config, delete_smtp_config, add_audit_log
)
from app.services.email import EmailService, EmailMessage

router = APIRouter(prefix="/smtp", tags=["smtp"])


@router.get("/api/smtp")
async def list_smtp_api(
    current_user: dict = Depends(require_any_user),
):
    """List all SMTP configs (API)."""
    configs = get_smtp_configs()
    
    return [
        {
            "id": c['id'],
            "name": c['name'],
            "server": c['server'],
            "port": c['port'],
            "username": c['username'],
            "use_tls": c.get('use_tls', True),
            "from_address": c['from_address'],
            "from_name": c.get('from_name'),
            "is_default": c.get('is_default', False),
            "is_active": c.get('is_active', True)
        }
        for c in configs
    ]


@router.get("/api/smtp/{config_id}")
async def get_smtp_api(
    config_id: int,
    current_user: dict = Depends(require_any_user),
):
    """Get SMTP config details (API)."""
    config = get_smtp_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="SMTP config not found")
    
    return config


@router.post("/api/smtp")
async def create_smtp_api(
    config_data: dict,
    current_user: dict = Depends(require_master_admin),
):
    """Create a new SMTP config (API)."""
    new_config = create_smtp_config(
        name=config_data.get("name"),
        server=config_data.get("server"),
        port=config_data.get("port", 587),
        username=config_data.get("username"),
        password=config_data.get("password"),
        from_address=config_data.get("from_address"),
        from_name=config_data.get("from_name"),
        use_tls=config_data.get("use_tls", True),
        is_default=config_data.get("is_default", False),
        is_active=config_data.get("is_active", True)
    )
    
    # Audit log
    add_audit_log(
        action='create',
        target_type='smtp',
        target_id=str(new_config['id']),
        details=f"Created SMTP config '{new_config['name']}' ({new_config['server']}:{new_config['port']})",
        user_id=current_user.get('id'),
        username=current_user.get('username')
    )
    
    return {
        "id": new_config['id'],
        "name": new_config['name'],
        "message": "SMTP config created successfully"
    }


@router.put("/api/smtp/{config_id}")
async def update_smtp_api(
    config_id: int,
    config_data: dict,
    current_user: dict = Depends(require_master_admin),
):
    """Update an SMTP config (API)."""
    config = get_smtp_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="SMTP config not found")
    
    update_smtp_config(config_id, config_data)
    
    # Audit log
    change_details = [f"{k}='{v}'" for k, v in config_data.items() if k not in ('updated_at', 'password')]
    add_audit_log(
        action='update',
        target_type='smtp',
        target_id=str(config_id),
        details=f"Updated SMTP config '{config['name']}': {', '.join(change_details)}" if change_details else f"Updated SMTP config '{config['name']}'",
        user_id=current_user.get('id'),
        username=current_user.get('username')
    )
    
    return {"message": "SMTP config updated successfully"}


@router.delete("/api/smtp/{config_id}")
async def delete_smtp_api(
    config_id: int,
    current_user: dict = Depends(require_master_admin),
):
    """Delete an SMTP config (API)."""
    config = get_smtp_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="SMTP config not found")
    
    if delete_smtp_config(config_id):
        # Audit log
        add_audit_log(
            action='delete',
            target_type='smtp',
            target_id=str(config_id),
            details=f"Deleted SMTP config '{config['name']}' ({config['server']}:{config['port']})",
            user_id=current_user.get('id'),
            username=current_user.get('username')
        )
        return {"message": "SMTP config deleted successfully"}
    raise HTTPException(status_code=404, detail="SMTP config not found")


@router.post("/api/smtp/{config_id}/test")
async def test_smtp_api(
    config_id: int,
    test_data: dict,
    current_user: dict = Depends(require_master_admin),
):
    """Test SMTP config by sending a test email."""
    config = get_smtp_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="SMTP config not found")
    
    test_email = test_data.get("email")
    if not test_email:
        raise HTTPException(status_code=400, detail="Test email address is required")
    
    try:
        # Create email service from config
        email_service = EmailService(
            server=config["server"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            use_tls=config.get("use_tls", True),
            from_address=config["from_address"],
            from_name=config.get("from_name", "Report Generator")
        )
        
        # Build test email message
        subject = "SMTP Test Email - Therefore Report Generator"
        body_html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .success {{ color: #28a745; font-weight: bold; }}
        .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #6c757d; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header - Outlook Compatible -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #667eea;">
            <tr>
                <td style="padding: 20px; text-align: center; color: white;">
                    <h1 style="margin: 0; font-size: 24px;">SMTP Test Successful</h1>
                </td>
            </tr>
        </table>
        
        <!-- Content - Outlook Compatible -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 20px;">
            <tr>
                <td style="padding: 20px; background-color: #f8f9fa;">
                    <p>Hello,</p>
                    <p>This is a test email from the <strong>Therefore Report Generator</strong> to verify your SMTP configuration.</p>
                    <p style="color: #28a745; font-weight: bold;">Your SMTP settings are working correctly!</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p><strong>Configuration Details:</strong></p>
                    <ul>
                        <li><strong>Name:</strong> {config["name"]}</li>
                        <li><strong>Server:</strong> {config["server"]}:{config["port"]}</li>
                        <li><strong>From:</strong> {config.get("from_name", "Report Generator")} &lt;{config["from_address"]}&gt;</li>
                        <li><strong>TLS:</strong> {"Enabled" if config.get("use_tls", True) else "Disabled"}</li>
                    </ul>
                </td>
            </tr>
        </table>
        
        <div class="footer">
            <p>Test initiated by: {current_user.get("username", "Unknown")}</p>
            <p><small>This is an automated test message. Please do not reply.</small></p>
        </div>
    </div>
</body>
</html>"""
        
        message = EmailMessage(
            to_address=test_email,
            from_address=config["from_address"],
            subject=subject,
            body_html=body_html,
            from_name=config.get("from_name", "Report Generator")
        )
        
        # Send the test email
        success = await email_service.send(message)
        
        if success:
            return {"success": True, "message": f"Test email sent successfully to {test_email}"}
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "Failed to send test email. Please check your SMTP configuration and try again."}
            )
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error sending test email: {str(e)}"}
        )


@router.post("/api/smtp/test")
async def test_smtp_unsaved_api(
    test_data: dict,
    current_user: dict = Depends(require_master_admin),
):
    """Test SMTP config with unsaved data (for testing before creating/saving)."""
    config_data = test_data.get("config", {})
    test_email = test_data.get("email")
    
    if not test_email:
        raise HTTPException(status_code=400, detail="Test email address is required")
    
    # Validate required fields
    required_fields = ["server", "port", "username", "password", "from_address"]
    missing = [f for f in required_fields if not config_data.get(f)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing)}")
    
    try:
        # Create email service from provided config data
        email_service = EmailService(
            server=config_data["server"],
            port=int(config_data["port"]),
            username=config_data["username"],
            password=config_data["password"],
            use_tls=config_data.get("use_tls", True),
            from_address=config_data["from_address"],
            from_name=config_data.get("from_name", "Report Generator")
        )
        
        # Build test email message
        config_name = config_data.get("name", "Unsaved Configuration")
        subject = "SMTP Test Email - Therefore Report Generator"
        body_html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .success {{ color: #28a745; font-weight: bold; }}
        .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #6c757d; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header - Outlook Compatible -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #667eea;">
            <tr>
                <td style="padding: 20px; text-align: center; color: white;">
                    <h1 style="margin: 0; font-size: 24px;">SMTP Test Successful</h1>
                </td>
            </tr>
        </table>
        
        <!-- Content - Outlook Compatible -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 20px;">
            <tr>
                <td style="padding: 20px; background-color: #f8f9fa;">
                    <!-- Unsaved notice -->
                    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 15px;">
                        <tr>
                            <td style="background-color: #fff3cd; color: #856404; padding: 10px;">
                                <strong>Note:</strong> This is a test of unsaved configuration settings.
                            </td>
                        </tr>
                    </table>
                    <p>Hello,</p>
                    <p>This is a test email from the <strong>Therefore Report Generator</strong> to verify your SMTP configuration.</p>
                    <p style="color: #28a745; font-weight: bold;">Your SMTP settings are working correctly!</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p><strong>Configuration Details:</strong></p>
                    <ul>
                        <li><strong>Name:</strong> {config_name}</li>
                        <li><strong>Server:</strong> {config_data["server"]}:{config_data["port"]}</li>
                        <li><strong>From:</strong> {config_data.get("from_name", "Report Generator")} &lt;{config_data["from_address"]}&gt;</li>
                        <li><strong>TLS:</strong> {"Enabled" if config_data.get("use_tls", True) else "Disabled"}</li>
                    </ul>
                </td>
            </tr>
        </table>
        
        <div class="footer">
            <p>Test initiated by: {current_user.get("username", "Unknown")}</p>
            <p><small>This is an automated test message. Please do not reply.</small></p>
        </div>
    </div>
</body>
</html>"""
        
        message = EmailMessage(
            to_address=test_email,
            from_address=config_data["from_address"],
            subject=subject,
            body_html=body_html,
            from_name=config_data.get("from_name", "Report Generator")
        )
        
        # Send the test email
        success = await email_service.send(message)
        
        if success:
            return {"success": True, "message": f"Test email sent successfully to {test_email}"}
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "Failed to send test email. Please check your SMTP configuration and try again."}
            )
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error sending test email: {str(e)}"}
        )


# HTML Routes

@router.get("", response_class=HTMLResponse)
async def smtp_page(
    request: Request,
    current_user: dict = Depends(require_master_admin),
):
    """SMTP configs list page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    configs = get_smtp_configs()
    
    return templates.TemplateResponse("smtp/list.html", {
        "request": request,
        "user": current_user,
        "configs": configs
    })


@router.get("/new", response_class=HTMLResponse)
async def new_smtp_page(
    request: Request,
    current_user: dict = Depends(require_master_admin)
):
    """New SMTP config form."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("smtp/form.html", {
        "request": request,
        "user": current_user,
        "config": None
    })


@router.get("/{config_id}/edit", response_class=HTMLResponse)
async def edit_smtp_page(
    config_id: int,
    request: Request,
    current_user: dict = Depends(require_master_admin),
):
    """Edit SMTP config form."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    config = get_smtp_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="SMTP config not found")
    
    return templates.TemplateResponse("smtp/form.html", {
        "request": request,
        "user": current_user,
        "config": config
    })


@router.post("", response_class=HTMLResponse)
async def create_smtp_form(
    request: Request,
    current_user: dict = Depends(require_master_admin),
):
    """Create SMTP config from form."""
    form = await request.form()
    
    new_config = create_smtp_config(
        name=form.get("name"),
        server=form.get("server"),
        port=int(form.get("port", 587)),
        username=form.get("username"),
        password=form.get("password"),
        from_address=form.get("from_address"),
        from_name=form.get("from_name"),
        use_tls=form.get("use_tls") == "on",
        is_default=form.get("is_default") == "on",
        is_active=form.get("is_active") == "on"
    )
    
    # Audit log
    add_audit_log(
        action='create',
        target_type='smtp',
        target_id=str(new_config['id']),
        details=f"Created SMTP config '{new_config['name']}' ({new_config['server']}:{new_config['port']})",
        user_id=current_user.get('id'),
        username=current_user.get('username')
    )
    
    return RedirectResponse(url="/smtp", status_code=302)


@router.post("/{config_id}", response_class=HTMLResponse)
async def update_smtp_form(
    config_id: int,
    request: Request,
    current_user: dict = Depends(require_master_admin),
):
    """Update SMTP config from form."""
    config = get_smtp_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="SMTP config not found")
    
    form = await request.form()
    
    updates = {
        'name': form.get("name"),
        'server': form.get("server"),
        'port': int(form.get("port", 587)),
        'username': form.get("username"),
        'use_tls': form.get("use_tls") == "on",
        'from_address': form.get("from_address"),
        'from_name': form.get("from_name"),
        'is_default': form.get("is_default") == "on",
        'is_active': form.get("is_active") == "on"
    }
    
    if form.get("password"):
        updates['password'] = form.get("password")
    
    update_smtp_config(config_id, updates)
    
    # Audit log
    add_audit_log(
        action='update',
        target_type='smtp',
        target_id=str(config_id),
        details=f"Updated SMTP config '{config['name']}'",
        user_id=current_user.get('id'),
        username=current_user.get('username')
    )
    
    return RedirectResponse(url="/smtp", status_code=302)


@router.post("/{config_id}/delete", response_class=HTMLResponse)
async def delete_smtp_form(
    config_id: int,
    current_user: dict = Depends(require_master_admin),
):
    """Delete SMTP config from form."""
    config = get_smtp_config_by_id(config_id)
    if config:
        delete_smtp_config(config_id)
        
        # Audit log
        add_audit_log(
            action='delete',
            target_type='smtp',
            target_id=str(config_id),
            details=f"Deleted SMTP config '{config['name']}' ({config['server']}:{config['port']})",
            user_id=current_user.get('id'),
            username=current_user.get('username')
        )
    return RedirectResponse(url="/smtp", status_code=302)
