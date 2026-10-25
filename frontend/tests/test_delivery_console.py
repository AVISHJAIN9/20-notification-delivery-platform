import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.database import Base, get_db
from api.app import app


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


def test_frontend_assets_exist():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    src_dir = os.path.join(base_dir, "src")

    html_path = os.path.join(src_dir, "index.html")
    css_path = os.path.join(src_dir, "index.css")
    js_path = os.path.join(src_dir, "app.js")

    assert os.path.exists(html_path), "index.html must exist"
    assert os.path.exists(css_path), "index.css must exist"
    assert os.path.exists(js_path), "app.js must exist"


def test_html_structure_and_ids():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    html_path = os.path.join(base_dir, "src", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Metric KPI elements
    assert 'id="val-delivered"' in content
    assert 'id="val-queued"' in content
    assert 'id="val-suppressed"' in content
    assert 'id="val-failed"' in content

    # Form elements
    assert 'id="notification-form"' in content
    assert 'id="input-channel"' in content
    assert 'id="input-recipient"' in content
    assert 'id="input-priority"' in content
    assert 'id="input-body"' in content
    assert 'id="btn-submit-dispatch"' in content

    # Table feed elements
    assert 'id="delivery-table"' in content
    assert 'id="delivery-tbody"' in content
    assert 'id="filter-channel"' in content


def test_css_styling_and_tokens():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    css_path = os.path.join(base_dir, "src", "index.css")
    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "--accent-primary" in content
    assert "glass-panel" in content
    assert "status-DELIVERED" in content
    assert "status-SUPPRESSED" in content
    assert "metrics-grid" in content


@pytest.mark.asyncio
async def test_javascript_console_contract(client):
    base_dir = os.path.dirname(os.path.dirname(__file__))
    js_path = os.path.join(base_dir, "src", "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "fetchDeliveryFeed" in content
    assert "addNotificationToFeed" in content
    assert "updateMetrics" in content
    assert "/notifications/dispatch" in content

    # Verify that the payload app.js sends is accepted by the backend API
    payload = {
        "user_id": "usr-ui-99",
        "channel": "EMAIL",
        "recipient": "ui-test@example.com",
        "priority": "HIGH",
        "subject": "UI Security Notice",
        "body": "Verifying console dispatch contract",
        "category": "ACCOUNT_SECURITY"
    }
    res = await client.post("/notifications/dispatch", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["notification_id"].startswith("ntf_")
    assert data["status"] in ["DELIVERED", "QUEUED", "PENDING"]
    assert data["recipient"] == "ui-test@example.com"

    # Verify feed list endpoint returns the dispatched record
    list_res = await client.get("/notifications")
    assert list_res.status_code == 200
    records = list_res.json()
    assert len(records) >= 1
    assert any(r["notification_id"] == data["notification_id"] for r in records)
