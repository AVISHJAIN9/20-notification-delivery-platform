"""
Tests for Security, RBAC, Tenant Isolation, and Audit Logging (NTF-125, NTF-126, NTF-127, NTF-133).
- NTF-125: API authentication
- NTF-126: RBAC
- NTF-127: Tenant isolation
- NTF-133: Audit logging
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi import FastAPI, Depends, HTTPException

from db.database import Base, get_db
from models.store import NotificationStoreManager
from security.auth import (
    authenticate_request,
    require_permission,
    AuthContext,
    Permission,
    Role
)


@pytest_asyncio.fixture
async def sec_app_and_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    test_app = FastAPI()

    async def override_get_db():
        async with session_maker() as session:
            yield session

    test_app.dependency_overrides[get_db] = override_get_db

    @test_app.get("/secure/ping")
    async def ping_endpoint(auth: AuthContext = Depends(authenticate_request)):
        return {"ping": "pong", "tenant_id": auth.tenant_id, "role": auth.role}

    @test_app.post("/secure/admin-only")
    async def admin_endpoint(auth: AuthContext = Depends(require_permission(Permission.PROVIDER_MANAGE))):
        return {"status": "ok", "admin_executed": True}

    @test_app.post("/secure/operator-action")
    async def operator_endpoint(auth: AuthContext = Depends(require_permission(Permission.NOTIFICATION_SEND))):
        return {"status": "ok", "operator_executed": True}

    @test_app.get("/secure/tenant-data/{target_tenant_id}")
    async def tenant_data_endpoint(
        target_tenant_id: str,
        auth: AuthContext = Depends(authenticate_request)
    ):
        auth.verify_tenant(target_tenant_id)
        return {"tenant_id": target_tenant_id, "data": "secret_data"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session_maker

    test_app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_NTF_125_api_authentication(sec_app_and_session):
    """
    NTF-125: API authentication.
    Tests API key authentication with hashed keys, missing key rejection, and revoked key rejection.
    """
    client, session_maker = sec_app_and_session

    async with session_maker() as session:
        store = NotificationStoreManager(session)
        key_schema, raw_key = await store.create_api_key(
            tenant_id="tenant-auth-1",
            name="Primary Service Key",
            role="OPERATOR"
        )
        revoked_schema, raw_revoked_key = await store.create_api_key(
            tenant_id="tenant-auth-1",
            name="Revoked Key",
            role="OPERATOR"
        )
        await store.revoke_api_key(tenant_id="tenant-auth-1", key_id=revoked_schema.id)

    # 1. Missing API key -> 401
    res_missing = await client.get("/secure/ping")
    assert res_missing.status_code == 401
    assert "Missing API Key" in res_missing.json()["detail"]

    # 2. Invalid API key -> 401
    res_invalid = await client.get("/secure/ping", headers={"X-API-Key": "ntf_invalid_random_string"})
    assert res_invalid.status_code == 401
    assert "Invalid or revoked API Key" in res_invalid.json()["detail"]

    # 3. Revoked API key -> 401
    res_revoked = await client.get("/secure/ping", headers={"X-API-Key": raw_revoked_key})
    assert res_revoked.status_code == 401

    # 4. Valid API key in X-API-Key header -> 200
    res_valid = await client.get("/secure/ping", headers={"X-API-Key": raw_key})
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert data["tenant_id"] == "tenant-auth-1"
    assert data["role"] == "OPERATOR"

    # 5. Valid API key in Authorization: Bearer header -> 200
    res_bearer = await client.get("/secure/ping", headers={"Authorization": f"Bearer {raw_key}"})
    assert res_bearer.status_code == 200


@pytest.mark.asyncio
async def test_NTF_126_rbac(sec_app_and_session):
    """
    NTF-126: Role-Based Access Control (RBAC).
    Tests permission enforcement across ADMIN, OPERATOR, and VIEWER roles.
    """
    client, session_maker = sec_app_and_session

    async with session_maker() as session:
        store = NotificationStoreManager(session)
        _, admin_key = await store.create_api_key(tenant_id="t1", name="Admin", role="ADMIN")
        _, operator_key = await store.create_api_key(tenant_id="t1", name="Operator", role="OPERATOR")
        _, viewer_key = await store.create_api_key(tenant_id="t1", name="Viewer", role="VIEWER")

    # 1. Admin can access admin endpoint and operator endpoint
    res_admin_on_admin = await client.post("/secure/admin-only", headers={"X-API-Key": admin_key})
    assert res_admin_on_admin.status_code == 200

    res_admin_on_op = await client.post("/secure/operator-action", headers={"X-API-Key": admin_key})
    assert res_admin_on_op.status_code == 200

    # 2. Operator can access operator endpoint, but DENIED on admin endpoint -> 403
    res_op_on_op = await client.post("/secure/operator-action", headers={"X-API-Key": operator_key})
    assert res_op_on_op.status_code == 200

    res_op_on_admin = await client.post("/secure/admin-only", headers={"X-API-Key": operator_key})
    assert res_op_on_admin.status_code == 403
    assert "lacks required permission" in res_op_on_admin.json()["detail"]

    # 3. Viewer is DENIED on both operator and admin endpoints -> 403
    res_view_on_op = await client.post("/secure/operator-action", headers={"X-API-Key": viewer_key})
    assert res_view_on_op.status_code == 403

    res_view_on_admin = await client.post("/secure/admin-only", headers={"X-API-Key": viewer_key})
    assert res_view_on_admin.status_code == 403


@pytest.mark.asyncio
async def test_NTF_127_tenant_isolation(sec_app_and_session):
    """
    NTF-127: Tenant isolation.
    Tests that a valid API key for tenant A is denied access when requesting tenant B resources.
    """
    client, session_maker = sec_app_and_session

    async with session_maker() as session:
        store = NotificationStoreManager(session)
        _, tenant_a_key = await store.create_api_key(tenant_id="tenant-alpha", name="Alpha Key", role="ADMIN")
        _, tenant_b_key = await store.create_api_key(tenant_id="tenant-beta", name="Beta Key", role="ADMIN")

    # 1. Tenant Alpha accesses its own data -> 200
    res_alpha_self = await client.get("/secure/tenant-data/tenant-alpha", headers={"X-API-Key": tenant_a_key})
    assert res_alpha_self.status_code == 200
    assert res_alpha_self.json()["tenant_id"] == "tenant-alpha"

    # 2. Tenant Alpha attempts to access Tenant Beta data -> 403 Forbidden
    res_cross_access = await client.get("/secure/tenant-data/tenant-beta", headers={"X-API-Key": tenant_a_key})
    assert res_cross_access.status_code == 403
    assert "cannot access resources for tenant 'tenant-beta'" in res_cross_access.json()["detail"]

    # 3. Tenant Beta accesses its own data -> 200
    res_beta_self = await client.get("/secure/tenant-data/tenant-beta", headers={"X-API-Key": tenant_b_key})
    assert res_beta_self.status_code == 200


@pytest.mark.asyncio
async def test_NTF_133_audit_logging(sec_app_and_session):
    """
    NTF-133: Audit logging.
    Tests recording audit log events for administrative mutations and querying audit history.
    """
    _, session_maker = sec_app_and_session

    async with session_maker() as session:
        store = NotificationStoreManager(session)

        # Record multiple audit events
        audit1 = await store.record_audit_event(
            audit_id="aud-133-1",
            tenant_id="tenant-audit",
            actor="admin@platform.com",
            action="TEMPLATE_APPROVED",
            resource_type="template",
            resource_id="tmpl-welcome-v2",
            details={"version": 2, "approved_reason": "QA passed"}
        )
        assert audit1.id == "aud-133-1"
        assert audit1.action == "TEMPLATE_APPROVED"

        audit2 = await store.record_audit_event(
            audit_id="aud-133-2",
            tenant_id="tenant-audit",
            actor="ops@platform.com",
            action="PROVIDER_FAILOVER",
            resource_type="provider",
            resource_id="sendgrid-primary",
            details={"switched_to": "mailgun-backup"}
        )
        assert audit2.id == "aud-133-2"

        # Query audit logs for tenant
        logs = await store.get_audit_logs(tenant_id="tenant-audit")
        assert len(logs) == 2
        actions = [l.action for l in logs]
        assert "TEMPLATE_APPROVED" in actions
        assert "PROVIDER_FAILOVER" in actions

        # Filter by resource_type
        tmpl_logs = await store.get_audit_logs(tenant_id="tenant-audit", resource_type="template")
        assert len(tmpl_logs) == 1
        assert tmpl_logs[0].resource_id == "tmpl-welcome-v2"
