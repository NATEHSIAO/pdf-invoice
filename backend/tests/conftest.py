import pytest
import os
import tempfile
from pathlib import Path
import sys
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
import httpx
from app.routes.auth import get_current_user, verify_token

# 加入專案根目錄到 Python 路徑
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir))

@pytest.fixture(scope="session")
def test_temp_dir():
    """建立測試用暫存目錄"""
    temp_dir = tempfile.mkdtemp(prefix="pdf_test_")
    yield temp_dir
    # 清理暫存目錄
    if os.path.exists(temp_dir):
        for root, dirs, files in os.walk(temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(temp_dir)

@pytest.fixture(scope="function")
def sample_pdf(test_temp_dir):
    """建立測試用 PDF 檔案"""
    pdf_path = Path(test_temp_dir) / "test.pdf"
    with open(pdf_path, "wb") as f:
        f.write(b"test pdf content")
    yield pdf_path
    if pdf_path.exists():
        pdf_path.unlink()

@pytest.fixture
def mock_email_service():
    """模擬郵件服務"""
    class MockEmailService:
        def __init__(self):
            self.provider = "GOOGLE"
            self.access_token = "test_token"
            self.base_url = "https://test.api"
    
    return MockEmailService()

@pytest.fixture
def mock_httpx_client():
    """模擬 HTTPX 客戶端"""
    class MockResponse:
        def __init__(self, status_code=200, content=b"", json_data=None):
            self.status_code = status_code
            self.content = content
            self._json = json_data

        def json(self):
            return self._json

    return MockResponse

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def mock_auth_header():
    return {"Authorization": "Bearer test_token"}

@pytest.fixture
def mock_user():
    return User(
        id="test_user",
        email="test@example.com",
        name="Test User",
        picture=None,
        provider="GOOGLE",
        access_token="test_token"
    )

@pytest.fixture(autouse=True)
async def override_dependencies(mock_user):
    async def override_get_current_user():
        return mock_user

    def override_verify_token(token: str):
        return {
            "id": mock_user.id,
            "email": mock_user.email,
            "name": mock_user.name,
            "provider": mock_user.provider
        }

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[verify_token] = override_verify_token
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def mock_current_user(mock_user):
    async def get_current_user():
        return mock_user
    return get_current_user

@pytest.fixture
def mock_email_service(mock_user):
    class MockEmailService:
        def __init__(self):
            self.provider = mock_user.provider
            self.access_token = mock_user.access_token
            self.base_url = "https://test.api"
            self.client = httpx.AsyncClient()
    return MockEmailService() 