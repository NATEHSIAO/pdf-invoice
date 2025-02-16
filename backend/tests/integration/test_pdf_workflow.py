import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, AsyncMock, Mock
import os
from fastapi import HTTPException
from backend.app.routes.pdf import AnalysisProgress, AnalysisResult, get_current_user
from app.models.user import User

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def mock_token():
    return "test_token"

@pytest.fixture
def mock_auth_header(mock_token):
    return {"Authorization": f"Bearer {mock_token}"}

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

@pytest.mark.integration
@pytest.mark.parametrize("provider", ["GOOGLE", "MICROSOFT"])
async def test_complete_pdf_workflow(test_client, mock_auth_header, mock_user, provider):
    """測試不同提供者的完整 PDF 處理流程"""
    mock_user.provider = provider
    
    with patch("app.routes.pdf.EmailService") as mock_email_service, \
         patch("app.routes.pdf.download_pdf_attachment") as mock_download, \
         patch("app.routes.pdf.extract_invoice_data") as mock_extract:
        
        mock_service = AsyncMock()
        mock_email_service.return_value = mock_service
        mock_service.provider = provider
        mock_service.access_token = mock_user.access_token
        
        mock_service.search_emails.return_value = [{
            "id": "test_email_id",
            "subject": "Test Invoice"
        }]
        
        mock_service.get_email_details.return_value = {
            "attachments": [{
                "filename": "test.pdf",
                "attachmentId": "1",
                "mimeType": "application/pdf"
            }],
            "subject": "Test Invoice",
            "from": "test@example.com",
            "date": "2024-03-01"
        }
        
        mock_download.return_value = "/tmp/test.pdf"
        mock_extract.return_value = {
            "email_subject": "Test Invoice",
            "email_sender": "test@example.com",
            "email_date": "2024-03-01",
            "invoice_number": "TEST123",
            "invoice_date": "2024-03-01",
            "buyer_name": "測試公司",
            "buyer_tax_id": "12345678",
            "seller_name": "供應商",
            "taxable_amount": 10000.0,
            "tax_free_amount": 0.0,
            "zero_tax_amount": 0.0,
            "tax_amount": 500.0,
            "total_amount": 10500.0
        }
        
        response = test_client.post(
            "/api/pdf/analyze",
            headers=mock_auth_header,
            json=["test_email_id"]
        )
        assert response.status_code == 200

@pytest.mark.parametrize("error_scenario", [
    ("invalid_token", 401, "認證失敗"),
    ("permission_denied", 403, "權限不足"),
    ("rate_limit", 429, "請求過於頻繁")
])
def test_pdf_workflow_errors(test_client, mock_auth_header, error_scenario):
    """測試 PDF 處理流程中的錯誤處理"""
    scenario, expected_status, error_message = error_scenario

    if scenario == "invalid_token":
        # 覆寫 get_current_user 使其拋出例外
        test_client.app.dependency_overrides[get_current_user] = lambda: (_ for _ in ()).throw(
            HTTPException(status_code=401, detail="認證失敗")
        )
        with patch("app.routes.pdf.EmailService") as mock_email_service:
            response = test_client.post(
                "/api/pdf/analyze",
                headers=mock_auth_header,
                json=["test_email_id"]
            )
        # 清除 override
        test_client.app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == expected_status

    else:
        # 模擬 permission_denied 或 rate_limit 情境：設定 get_email_details 拋出相應 HTTPException
        with patch("app.routes.pdf.EmailService") as mock_email_service:
            mock_service = AsyncMock()
            mock_service.get_email_details.side_effect = HTTPException(
                status_code=expected_status,
                detail=error_message
            )
            mock_email_service.return_value = mock_service

            response = test_client.post(
                "/api/pdf/analyze",
                headers=mock_auth_header,
                json=["test_email_id"]
            )
            assert response.status_code == expected_status

@pytest.mark.asyncio
async def test_pdf_progress_tracking(test_client, mock_auth_header):
    """測試 PDF 處理進度追蹤"""
    with patch("app.routes.pdf.analyze_pdfs") as mock_analyze:
        # 模擬長時間運行的處理過程
        mock_analyze.return_value = {
            "invoices": [],
            "failed_files": [],
            "download_url": "/api/pdf/download/test"
        }
        
        # 開始分析
        response = test_client.post(
            "/api/pdf/analyze",
            headers=mock_auth_header,
            json=["test_email_id"]
        )
        assert response.status_code == 200
        
        # 檢查進度
        progress_response = test_client.get("/api/pdf/progress")
        assert progress_response.status_code == 200
        progress_data = progress_response.json()
        assert "total" in progress_data
        assert "current" in progress_data
        assert "status" in progress_data 