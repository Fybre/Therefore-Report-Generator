"""Email template management routes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import require_master_admin, require_any_user
from app.store import (
    get_templates, get_template_by_id, create_template, update_template, delete_template
)
from app.services.email import create_default_templates

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/api/templates")
async def list_templates_api(
    current_user: dict = Depends(require_any_user),
):
    """List all templates (API)."""
    templates = get_templates()
    
    return [
        {
            "id": t['id'],
            "name": t['name'],
            "description": t.get('description'),
            "subject_template": t['subject_template'],
            "is_default": t.get('is_default', False)
        }
        for t in templates
    ]


@router.get("/api/templates/{template_id}")
async def get_template_api(
    template_id: int,
    current_user: dict = Depends(require_any_user),
):
    """Get template details (API)."""
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template


@router.post("/api/templates")
async def create_template_api(
    template_data: dict,
    current_user: dict = Depends(require_master_admin),
):
    """Create a new template (API)."""
    new_template = create_template(
        name=template_data.get("name"),
        description=template_data.get("description"),
        subject_template=template_data.get("subject_template"),
        body_template=template_data.get("body_template"),
        is_default=template_data.get("is_default", False),
        created_by=current_user['id']
    )
    
    return {
        "id": new_template['id'],
        "name": new_template['name'],
        "message": "Template created successfully"
    }


@router.put("/api/templates/{template_id}")
async def update_template_api(
    template_id: int,
    template_data: dict,
    current_user: dict = Depends(require_master_admin),
):
    """Update a template (API)."""
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    update_template(template_id, template_data)
    return {"message": "Template updated successfully"}


@router.delete("/api/templates/{template_id}")
async def delete_template_api(
    template_id: int,
    current_user: dict = Depends(require_master_admin),
):
    """Delete a template (API)."""
    if delete_template(template_id):
        return {"message": "Template deleted successfully"}
    raise HTTPException(status_code=404, detail="Template not found")


# HTML Routes

@router.get("", response_class=HTMLResponse)
async def templates_page(
    request: Request,
    current_user: dict = Depends(require_any_user),
):
    """Templates list page."""
    from fastapi.templating import Jinja2Templates
    templates_jinja = Jinja2Templates(directory="templates")
    
    templates_list = get_templates()
    
    return templates_jinja.TemplateResponse("templates/list.html", {
        "request": request,
        "user": current_user,
        "templates": templates_list
    })


@router.get("/new", response_class=HTMLResponse)
async def new_template_page(
    request: Request,
    current_user: dict = Depends(require_master_admin)
):
    """New template form."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("templates/form.html", {
        "request": request,
        "user": current_user,
        "template": None
    })


@router.get("/{template_id}/edit", response_class=HTMLResponse)
async def edit_template_page(
    template_id: int,
    request: Request,
    current_user: dict = Depends(require_master_admin),
):
    """Edit template form."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return templates.TemplateResponse("templates/form.html", {
        "request": request,
        "user": current_user,
        "template": template
    })


@router.post("/init-defaults")
async def init_default_templates(
    current_user: dict = Depends(require_master_admin),
):
    """Initialize default templates (HTML form)."""
    default_templates = create_default_templates()
    existing = get_templates()
    existing_names = {t['name'] for t in existing}
    
    created_count = 0
    for key, (subject, body) in default_templates.items():
        name = key.replace("_", " ").title()
        if name in existing_names:
            continue
        
        create_template(
            name=name,
            description=f"Default template: {key}",
            subject_template=subject,
            body_template=body,
            is_default=(key == "all_instances"),
            created_by=current_user['id']
        )
        created_count += 1
    
    return RedirectResponse(
        url=f"/templates?message=Default+templates+initialized:+{created_count}+created",
        status_code=302
    )


@router.post("/api/reset-defaults")
async def reset_default_templates_api(
    current_user: dict = Depends(require_master_admin),
):
    """Delete all templates and recreate default templates (API)."""
    from app.store import delete_template, get_templates
    
    default_templates = create_default_templates()
    
    # Delete all existing templates
    existing = get_templates()
    for template in existing:
        delete_template(template['id'])
    
    # Create default templates
    created_count = 0
    for key, (subject, body) in default_templates.items():
        name = key.replace("_", " ").title()
        
        create_template(
            name=name,
            description=f"Default template: {key}",
            subject_template=subject,
            body_template=body,
            is_default=(key == "all_instances"),
            created_by=current_user['id']
        )
        created_count += 1
    
    return {
        "success": True,
        "message": f"All templates reset. Deleted {len(existing)}, created {created_count}.",
        "deleted": len(existing),
        "created": created_count
    }


@router.post("/reset-defaults")
async def reset_default_templates(
    current_user: dict = Depends(require_master_admin),
):
    """Delete all templates and recreate default templates (HTML form)."""
    from app.store import delete_template, get_templates
    
    default_templates = create_default_templates()
    
    # Delete all existing templates
    existing = get_templates()
    for template in existing:
        delete_template(template['id'])
    
    # Create default templates
    created_count = 0
    for key, (subject, body) in default_templates.items():
        name = key.replace("_", " ").title()
        
        create_template(
            name=name,
            description=f"Default template: {key}",
            subject_template=subject,
            body_template=body,
            is_default=(key == "all_instances"),
            created_by=current_user['id']
        )
        created_count += 1
    
    return RedirectResponse(
        url=f"/templates?message=Templates+reset:+{len(existing)}+deleted,+{created_count}+created",
        status_code=302
    )


@router.post("", response_class=HTMLResponse)
async def create_template_form(
    request: Request,
    current_user: dict = Depends(require_master_admin),
):
    """Create template from form."""
    form = await request.form()
    
    create_template(
        name=form.get("name"),
        description=form.get("description"),
        subject_template=form.get("subject_template"),
        body_template=form.get("body_template"),
        is_default=form.get("is_default") == "on",
        created_by=current_user['id']
    )
    
    return RedirectResponse(url="/templates", status_code=302)


@router.post("/{template_id}", response_class=HTMLResponse)
async def update_template_form(
    template_id: int,
    request: Request,
    current_user: dict = Depends(require_master_admin),
):
    """Update template from form."""
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    form = await request.form()
    
    updates = {
        'name': form.get("name"),
        'description': form.get("description"),
        'subject_template': form.get("subject_template"),
        'body_template': form.get("body_template"),
        'is_default': form.get("is_default") == "on"
    }
    
    update_template(template_id, updates)
    return RedirectResponse(url="/templates", status_code=302)


@router.post("/{template_id}/delete", response_class=HTMLResponse)
async def delete_template_form(
    template_id: int,
    current_user: dict = Depends(require_master_admin),
):
    """Delete template from form."""
    delete_template(template_id)
    return RedirectResponse(url="/templates", status_code=302)
