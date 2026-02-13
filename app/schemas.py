"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# ============== Base Schemas ==============

class UserBase(BaseModel):
    """Base user schema."""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    role: str = "user"
    is_active: bool = True


class TenantBase(BaseModel):
    """Base tenant schema."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool = True
    is_single_instance: bool = False


class EmailTemplateBase(BaseModel):
    """Base email template schema."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    subject_template: str = Field(..., min_length=1, max_length=500)
    body_template: str = Field(..., min_length=1)


class ReportBase(BaseModel):
    """Base report schema."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    workflow_processes: List[int] = []
    cron_schedule: str = Field(..., min_length=1, max_length=100)
    enabled: bool = True


class SMTPConfigBase(BaseModel):
    """Base SMTP config schema."""
    name: str = Field(..., min_length=1, max_length=100)
    server: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    username: str = Field(..., min_length=1, max_length=255)
    use_tls: bool = True
    from_address: str = Field(..., min_length=1, max_length=255)
    from_name: Optional[str] = Field(None, max_length=100)
    is_default: bool = False
    is_active: bool = True


# ============== Create Schemas ==============

class UserCreate(UserBase):
    """User creation schema."""
    password: str = Field(..., min_length=6)


class TenantCreate(TenantBase):
    """Tenant creation schema."""
    auth_token: Optional[str] = None


class EmailTemplateCreate(EmailTemplateBase):
    """Email template creation schema."""
    pass


class ReportCreate(ReportBase):
    """Report creation schema."""
    tenant_id: int
    template_id: int
    send_all_to_admin: bool = False
    admin_email: Optional[str] = None
    is_error_report: bool = False
    error_to_email: Optional[str] = None
    error_cc_email: Optional[str] = None
    timezone: Optional[str] = Field(default="Australia/Sydney", max_length=50)


class SMTPConfigCreate(SMTPConfigBase):
    """SMTP config creation schema."""
    password: str = Field(..., min_length=1)


# ============== Update Schemas ==============

class UserUpdate(BaseModel):
    """User update schema."""
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)


class TenantUpdate(BaseModel):
    """Tenant update schema."""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    base_url: Optional[str] = None
    auth_token: Optional[str] = None
    is_active: Optional[bool] = None


class EmailTemplateUpdate(BaseModel):
    """Email template update schema."""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    subject_template: Optional[str] = Field(None, max_length=500)
    body_template: Optional[str] = None
    is_default: Optional[bool] = None


class ReportUpdate(BaseModel):
    """Report update schema."""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    workflow_processes: Optional[List[int]] = None
    cron_schedule: Optional[str] = Field(None, max_length=100)
    enabled: Optional[bool] = None
    send_all_to_admin: Optional[bool] = None
    admin_email: Optional[str] = None
    template_id: Optional[int] = None
    is_error_report: Optional[bool] = None
    error_to_email: Optional[str] = None
    error_cc_email: Optional[str] = None
    timezone: Optional[str] = Field(None, max_length=50)


class SMTPConfigUpdate(BaseModel):
    """SMTP config update schema."""
    name: Optional[str] = Field(None, max_length=100)
    server: Optional[str] = Field(None, max_length=255)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = None
    use_tls: Optional[bool] = None
    from_address: Optional[str] = Field(None, max_length=255)
    from_name: Optional[str] = Field(None, max_length=100)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


# ============== Auth Schemas ==============

class Token(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Login request schema."""
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""
    current_password: str
    new_password: str = Field(..., min_length=6)


# ============== Run Report Schemas ==============

class RunReportResponse(BaseModel):
    """Manual run report response."""
    success: bool
    message: str
    instances_found: int = 0
    emails_sent: int = 0
    emails_failed: int = 0
