"""
Authentication, RBAC, and Tenant Isolation (NTF-125, NTF-126, NTF-127).
- NTF-125: API authentication via hashed API keys.
- NTF-126: Role-Based Access Control (RBAC) with deny-by-default permission checks.
- NTF-127: Adversarial tenant isolation preventing cross-tenant data access.
"""

import hashlib
from typing import Optional, Set, Dict, Any
from enum import Enum
from pydantic import BaseModel
from fastapi import HTTPException, status, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from models.store import NotificationStoreManager, ApiKeySchema
from db.database import get_db


class Role(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class Permission(str, Enum):
    NOTIFICATION_SEND = "notification:send"
    NOTIFICATION_READ = "notification:read"
    NOTIFICATION_RETRY = "notification:retry"
    TEMPLATE_WRITE = "template:write"
    TEMPLATE_READ = "template:read"
    PROVIDER_MANAGE = "provider:manage"
    AUDIT_READ = "audit:read"


ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    Role.ADMIN.value: {
        Permission.NOTIFICATION_SEND.value,
        Permission.NOTIFICATION_READ.value,
        Permission.NOTIFICATION_RETRY.value,
        Permission.TEMPLATE_WRITE.value,
        Permission.TEMPLATE_READ.value,
        Permission.PROVIDER_MANAGE.value,
        Permission.AUDIT_READ.value,
    },
    Role.OPERATOR.value: {
        Permission.NOTIFICATION_SEND.value,
        Permission.NOTIFICATION_READ.value,
        Permission.NOTIFICATION_RETRY.value,
        Permission.TEMPLATE_READ.value,
    },
    Role.VIEWER.value: {
        Permission.NOTIFICATION_READ.value,
        Permission.TEMPLATE_READ.value,
    },
}


class AuthContext(BaseModel):
    tenant_id: str
    key_id: str
    role: str
    name: str

    def has_permission(self, permission: str) -> bool:
        allowed = ROLE_PERMISSIONS.get(self.role.upper(), set())
        return permission in allowed

    def verify_tenant(self, target_tenant_id: str) -> None:
        """
        Enforces tenant isolation (NTF-127).
        Raises 403 if target tenant does not match the authenticated tenant.
        """
        if self.tenant_id != target_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: cannot access resources for tenant '{target_tenant_id}'"
            )


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def authenticate_request(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    session: AsyncSession = Depends(get_db)
) -> AuthContext:
    """
    Validates API key from X-API-Key header or Authorization: Bearer <key> (NTF-125).
    """
    raw_key = None
    if x_api_key:
        raw_key = x_api_key.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        raw_key = authorization[7:].strip()

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key in X-API-Key or Authorization header"
        )

    hashed = hash_key(raw_key)
    store = NotificationStoreManager(session)
    api_key_rec = await store.get_api_key_by_hash(hashed)
    if not api_key_rec or not api_key_rec.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API Key"
        )

    return AuthContext(
        tenant_id=api_key_rec.tenant_id,
        key_id=api_key_rec.id,
        role=api_key_rec.role,
        name=api_key_rec.name
    )


def require_permission(perm: Permission):
    """
    FastAPI dependency factory enforcing RBAC (NTF-126).
    """
    async def dependency(auth: AuthContext = Depends(authenticate_request)) -> AuthContext:
        if not auth.has_permission(perm.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{auth.role}' lacks required permission '{perm.value}'"
            )
        return auth
    return dependency
