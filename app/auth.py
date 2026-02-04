"""Authentication utilities."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt

from app.config import get_settings
from app.store import get_user_by_email, verify_password

# JWT settings
settings = get_settings()
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

# Security scheme
security = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_token_from_request(request: Request) -> Optional[str]:
    """Extract token from request (header or cookie)."""
    # Try Authorization header first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]  # Remove "Bearer " prefix
    
    # Try cookie
    return request.cookies.get("access_token")


async def get_current_user_from_request(request: Request) -> Optional[dict]:
    """Get current user from request (for direct use, not as dependency)."""
    token = get_token_from_request(request)
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None
    
    user = get_user_by_email(email)
    if not user or not user.get('is_active', True):
        return None
    
    return user


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """Get the current user from token (as FastAPI dependency)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # First try to get token from Authorization header
    token = None
    if credentials:
        token = credentials.credentials
    
    # If no token in header, try cookie
    if not token:
        token = request.cookies.get("access_token")
    
    if not token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get user from store by email
    user = get_user_by_email(email)
    
    if user is None:
        raise credentials_exception
    
    if not user.get('is_active', True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Get current active user."""
    return current_user


class RoleChecker:
    """Check if user has required role."""
    
    def __init__(self, allowed_roles: list):
        """Initialize with allowed roles."""
        self.allowed_roles = allowed_roles
    
    async def __call__(self, user: dict = Depends(get_current_user)) -> dict:
        """Check user role."""
        if user.get('role') not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return user


# Role dependencies
require_master_admin = RoleChecker(['master_admin'])
require_admin = RoleChecker(['master_admin', 'tenant_admin'])
require_any_user = RoleChecker(['master_admin', 'tenant_admin', 'user'])


def has_tenant_access(user: dict, tenant_id: int) -> bool:
    """Check if user has access to a tenant."""
    # Master admin has access to all
    if user.get('role') == 'master_admin':
        return True
    
    # Check if user is assigned to tenant
    for user_tenant in user.get('tenants', []):
        if user_tenant.get('tenant_id') == tenant_id:
            return True
    
    return False


def is_tenant_admin(user: dict, tenant_id: int) -> bool:
    """Check if user is admin for a specific tenant."""
    # Master admin is admin for all
    if user.get('role') == 'master_admin':
        return True
    
    # Check if user is tenant admin for this tenant
    for user_tenant in user.get('tenants', []):
        if user_tenant.get('tenant_id') == tenant_id:
            if user_tenant.get('role') in ['master_admin', 'tenant_admin']:
                return True
    
    return False


async def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate a user by email."""
    return verify_password(email, password)


async def create_admin_user():
    """Create the initial admin user if no users exist."""
    from app.store import get_users, save_yaml, USERS_FILE
    
    users = get_users()
    if users:
        return
    
    settings = get_settings()
    
    admin = {
        'id': 1,
        'username': settings.ADMIN_USERNAME,
        'email': settings.ADMIN_EMAIL,
        'password_hash': bcrypt.hashpw(settings.ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode(),
        'role': 'master_admin',
        'is_active': True,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
        'tenants': []
    }
    
    save_yaml(USERS_FILE, [admin])
    print(f"Created admin user: {settings.ADMIN_USERNAME}")
