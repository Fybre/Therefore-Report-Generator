"""Authentication routes."""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import (
    authenticate_user, 
    create_access_token, 
    get_current_user
)
from app.store import get_user_by_username, update_user, verify_password
from app.schemas import LoginRequest, Token, ChangePasswordRequest
import bcrypt

router = APIRouter(tags=["authentication"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, message: str = None):
    """Login page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse("login.html", {
        "request": request,
        "message": message
    })


@router.post("/auth/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
):
    """Login and get access token using email."""
    user = await authenticate_user(credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user['email']})
    
    # Set cookie for web UI
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=28800,  # 8 hours
        samesite="lax"
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/auth/logout")
async def logout(response: Response):
    """Logout and clear cookie."""
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


@router.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    return {
        "id": current_user['id'],
        "username": current_user['username'],
        "email": current_user.get('email'),
        "role": current_user['role'],
        "is_active": current_user.get('is_active', True)
    }


@router.post("/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    """Change current user's password."""
    # Verify current password
    if not bcrypt.checkpw(request.current_password.encode(), current_user['password_hash'].encode()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    new_hash = bcrypt.hashpw(request.new_password.encode(), bcrypt.gensalt()).decode()
    update_user(current_user['id'], {'password_hash': new_hash})
    
    return {"message": "Password changed successfully"}


@router.post("/auth/update-profile")
async def update_profile(
    data: dict,
    current_user: dict = Depends(get_current_user),
):
    """Update current user's profile (username/display name)."""
    username = data.get('username', '').strip()
    
    # Validate username (if provided, it shouldn't be empty)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Display name is required"
        )
    
    # Update username
    updates = {'username': username}
    update_user(current_user['id'], updates)
    
    return {"message": "Profile updated successfully", "username": username}


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """User profile page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user
    })


# ============== Password Reset ==============

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Forgot password page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@router.post("/auth/forgot-password")
async def forgot_password(data: dict):
    """Request password reset token.
    
    Always returns success to prevent username enumeration.
    If user exists with provided email, sends reset email.
    """
    from datetime import datetime, timedelta
    import secrets
    from app.store import get_user_by_email, create_password_reset_token, get_user_by_id
    from app.store import get_default_smtp_config
    from app.services.email import EmailService, EmailMessage
    from app.config import get_settings
    
    settings = get_settings()
    base_url = settings.BASE_URL.rstrip('/')
    
    email = data.get('email', '').strip()
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )
    
    # Find user by email
    user = get_user_by_email(email)
    
    if not user:
        # Return success even if user not found (prevent enumeration)
        return {
            "message": "If an account with this email exists, password reset instructions have been sent.",
            "email_sent": False
        }
    
    # Use the email from the user record
    user_email = user.get('email')
    if not user_email:
        # User exists but has no email - can't send reset
        return {
            "message": "If the user exists and has an email address, password reset instructions have been sent.",
            "email_sent": False,
            "note": "No email on file for this user. Please contact your administrator."
        }
    
    # Generate secure token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiration
    
    # Store token
    create_password_reset_token(user['id'], token, expires_at)
    
    # Try to send email
    smtp_config = get_default_smtp_config()
    email_sent = False
    
    if smtp_config:
        try:
            reset_link = f"{base_url}/reset-password?token={token}"
            subject = "Password Reset Request"
            
            # Create HTML email
            html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Password Reset</title></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 500px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c3e50;">Password Reset Request</h2>
        <p>Hello <strong>{user['username']}</strong>,</p>
        <p>You have requested to reset your password for the Therefore Report Generator.</p>
        <p style="margin: 25px 0;">
            <a href="{reset_link}" style="background: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">Reset Password</a>
        </p>
        <p style="color: #666; font-size: 14px;">Or copy and paste this link:<br>{reset_link}</p>
        <p style="color: #e74c3c; font-size: 14px;">This link will expire in 1 hour.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #666; font-size: 12px;">If you did not request this password reset, please ignore this email.</p>
        <p style="color: #666; font-size: 12px;">Therefore Report Generator</p>
    </div>
</body>
</html>"""
            
            # Create email service and send
            email_service = EmailService(
                server=smtp_config['server'],
                port=smtp_config['port'],
                username=smtp_config['username'],
                password=smtp_config['password'],
                use_tls=smtp_config.get('use_tls', True),
                from_address=smtp_config.get('from_address'),
                from_name=smtp_config.get('from_name', 'Report Generator')
            )
            
            message = EmailMessage(
                to_address=user_email,
                from_address=smtp_config.get('from_address', smtp_config['username']),
                subject=subject,
                body_html=html_body,
                from_name=smtp_config.get('from_name', 'Report Generator')
            )
            
            email_sent = await email_service.send(message)
        except Exception as e:
            print(f"[SMTP] Failed to send password reset email: {e}")
            email_sent = False
    
    return {
        "message": "If the user exists and has an email address, password reset instructions have been sent.",
        "email_sent": email_sent
    }


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = None):
    """Reset password page (with token validation)."""
    from fastapi.templating import Jinja2Templates
    from app.store import get_password_reset_token, get_user_by_id
    
    templates = Jinja2Templates(directory="templates")
    
    # Validate token
    error = None
    user = None
    
    if not token:
        error = "Invalid or missing reset token."
    else:
        token_record = get_password_reset_token(token)
        if not token_record:
            error = "Invalid or expired reset token. Please request a new one."
        else:
            user = get_user_by_id(token_record['user_id'])
            if not user:
                error = "User not found."
    
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token,
        "error": error,
        "user": user,
        "username": user['username'] if user else None
    })


@router.post("/auth/reset-password")
async def reset_password_with_token(data: dict):
    """Reset password using token."""
    from app.store import get_password_reset_token, mark_token_used, update_user, get_user_by_id
    
    token = data.get('token')
    new_password = data.get('new_password')
    
    if not token or not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token and new password are required"
        )
    
    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters"
        )
    
    # Validate token
    token_record = get_password_reset_token(token)
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Get user
    user = get_user_by_id(token_record['user_id'])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    update_user(user['id'], {'password_hash': new_hash})
    
    # Mark token as used
    mark_token_used(token)
    
    # Audit log
    from app.store import add_audit_log
    add_audit_log(
        action='reset_password',
        target_type='user',
        target_id=str(user['id']),
        details=f"User '{user['username']}' reset their password via self-service",
        user_id=user['id'],
        username=user['username']
    )
    
    return {"message": "Password reset successfully. You can now log in with your new password."}
