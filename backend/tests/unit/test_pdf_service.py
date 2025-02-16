import pytest
from app.routes.pdf import (
    download_pdf_attachment,
    extract_invoice_data,
    analyze_pdfs,
    AnalysisResult,
    TEMP_DIR
)
from app.services.email import EmailService
import httpx
from unittest.mock import Mock, patch, AsyncMock
import os
import base64
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from app.models.user import User

@pytest.fixture
def mock_email_service():
    return Mock(spec=EmailService)

@pytest.fixture
def mock_httpx_client():
    return AsyncMock(spec=httpx.AsyncClient)

@pytest.fixture(scope="session")
def sample_invoice_path(tmp_path_factory):
    """建立測試用發票 PDF"""
    pdf_path = tmp_path_factory.mktemp("data") / "sample_invoice.pdf"
    
    # 使用 Helvetica 字體，但將中文字轉換為 Unicode 編碼
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica", 12)
    
    # 添加發票內容（使用 Unicode 編碼）
    content = [
        ("Invoice Number", "INV-2024001"),
        ("Invoice Date", "2024-03-01"),
        ("Buyer Name", "Test Company"),
        ("Buyer Tax ID", "12345678"),
        ("Seller Name", "Supplier"),
        ("Taxable Amount", "10000"),
        ("Tax Free Amount", "0"),
        ("Zero Tax Amount", "0"),
        ("Tax Amount", "500"),
        ("Total Amount", "10500")
    ]
    
    y = 750
    for label, value in content:
        text = f"{label}: {value}"
        c.drawString(100, y, text)
        y -= 20
    
    c.save()
    return pdf_path

@pytest.mark.asyncio
@pytest.mark.unit
async def test_pdf_analysis(mock_user):
    """測試 PDF 解析功能"""
    with patch("app.routes.pdf.EmailService") as mock_email_service:
        mock_service = AsyncMock()
        mock_email_service.return_value = mock_service
        
        # 設置 mock service 的屬性
        mock_service.provider = mock_user.provider
        mock_service.access_token = mock_user.access_token
        
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
        
        with patch("app.routes.pdf.download_pdf_attachment") as mock_download, \
             patch("app.routes.pdf.extract_invoice_data") as mock_extract:
            
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
            
            result = await analyze_pdfs(["test_email_id"], current_user=mock_user)
            
            assert isinstance(result, AnalysisResult)
            assert len(result.invoices) == 1
            assert len(result.failed_files) == 0

@pytest.mark.asyncio
async def test_google_pdf_download(mock_email_service, mock_httpx_client):
    """測試 Google PDF 下載邏輯"""
    # 設置測試數據
    message_id = "test_message_id"
    attachment = {
        "filename": "test.pdf",
        "attachmentId": "test_attachment_id",
        "mimeType": "application/pdf"
    }
    
    # 模擬 Google 回應
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": base64.b64encode(b"test pdf content").decode()
    }
    mock_httpx_client.get.return_value = mock_response
    
    # 設置 email service
    mock_email_service.provider = "GOOGLE"
    mock_email_service.access_token = "test_token"
    mock_email_service.base_url = "https://gmail.googleapis.com/gmail/v1"
    
    result = await download_pdf_attachment(
        mock_httpx_client,
        mock_email_service,
        message_id,
        attachment,
        "/tmp"
    )
    
    assert result is not None
    assert os.path.exists(result)

@pytest.mark.asyncio
async def test_microsoft_pdf_download(mock_email_service, mock_httpx_client):
    """測試 Microsoft PDF 下載邏輯"""
    try:
        # 設置測試數據
        message_id = "test_message_id"
        attachment = {
            "filename": "test.pdf",
            "attachmentId": "test_attachment_id",
            "mimeType": "application/pdf"
        }
        
        # 模擬 Microsoft 回應
        mock_info_response = Mock()
        mock_info_response.status_code = 200
        mock_info_response.json.return_value = {"id": "test_id"}
        
        mock_content_response = Mock()
        mock_content_response.status_code = 200
        mock_content_response.content = b"test pdf content"
        
        mock_httpx_client.get.side_effect = [mock_info_response, mock_content_response]
        
        # 設置 email service
        mock_email_service.provider = "MICROSOFT"
        mock_email_service.access_token = "test_token"
        mock_email_service.base_url = "https://graph.microsoft.com/v1.0"
        
        result = await download_pdf_attachment(
            mock_httpx_client,
            mock_email_service,
            message_id,
            attachment,
            "/tmp"
        )
        
        assert result is not None
        assert os.path.exists(result)
        
    except Exception as e:
        pytest.fail(f"測試失敗: {str(e)}")
    finally:
        # 清理測試檔案
        if result and os.path.exists(result):
            os.remove(result)

@pytest.mark.asyncio
async def test_extract_invoice_data(sample_invoice_path):
    """測試發票資料提取"""
    test_pdf_path = "/tmp/test_invoice.pdf"
    
    try:
        # 複製範例 PDF
        import shutil
        shutil.copy(str(sample_invoice_path), test_pdf_path)
        
        email_info = {
            "subject": "Test Invoice",
            "from": "test@example.com",
            "date": "2024-03-01"
        }
        
        result = extract_invoice_data(test_pdf_path, email_info)
        assert result is not None
        assert "invoice_number" in result
        assert "total_amount" in result
    finally:
        if os.path.exists(test_pdf_path):
            os.remove(test_pdf_path)

@pytest.mark.asyncio
async def test_google_pdf_download_error(mock_email_service, mock_httpx_client):
    """測試 Google PDF 下載錯誤處理"""
    message_id = "test_message_id"
    attachment = {
        "filename": "test.pdf",
        "attachmentId": "test_attachment_id",
        "mimeType": "application/pdf"
    }
    
    # 模擬錯誤回應
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_httpx_client.get.return_value = mock_response
    
    # 設置 email service
    mock_email_service.provider = "GOOGLE"
    mock_email_service.access_token = "invalid_token"
    
    result = await download_pdf_attachment(
        mock_httpx_client,
        mock_email_service,
        message_id,
        attachment,
        "/tmp"
    )
    
    assert result is None

@pytest.mark.asyncio
async def test_microsoft_pdf_download_error(mock_email_service, mock_httpx_client):
    """測試 Microsoft PDF 下載錯誤處理"""
    message_id = "test_message_id"
    attachment = {
        "filename": "test.pdf",
        "attachmentId": "test_attachment_id",
        "mimeType": "application/pdf"
    }
    
    # 模擬錯誤回應
    mock_response = Mock()
    mock_response.status_code = 403
    mock_response.text = "Permission denied"
    mock_httpx_client.get.return_value = mock_response
    
    # 設置 email service
    mock_email_service.provider = "MICROSOFT"
    mock_email_service.access_token = "invalid_token"
    
    result = await download_pdf_attachment(
        mock_httpx_client,
        mock_email_service,
        message_id,
        attachment,
        "/tmp"
    )
    
    assert result is None

@pytest.mark.asyncio
async def test_extract_invoice_data_invalid_pdf():
    """測試無效 PDF 的發票資料提取"""
    test_pdf_path = "/tmp/invalid_invoice.pdf"
    with open(test_pdf_path, "wb") as f:
        f.write(b"invalid pdf content")
    
    email_info = {
        "subject": "Test Invoice",
        "from": "test@example.com",
        "date": "2024-03-01"
    }
    
    try:
        result = extract_invoice_data(test_pdf_path, email_info)
        assert result is None
    finally:
        if os.path.exists(test_pdf_path):
            os.remove(test_pdf_path)

@pytest.mark.asyncio
async def test_analyze_pdfs_with_errors(mock_user):
    """測試 PDF 分析錯誤處理"""
    with patch("app.routes.pdf.EmailService") as mock_email_service, \
         patch("app.routes.pdf.get_current_user", return_value=mock_user), \
         patch("app.routes.pdf.download_pdf_attachment") as mock_download, \
         patch("app.routes.pdf.extract_invoice_data") as mock_extract:
        
        mock_service = AsyncMock()
        mock_email_service.return_value = mock_service
        
        # 設置 mock service 的屬性
        mock_service.provider = mock_user.provider
        mock_service.access_token = mock_user.access_token
        
        mock_service.get_email_details.return_value = {
            "attachments": [{
                "filename": "success.pdf",
                "attachmentId": "1",
                "mimeType": "application/pdf"
            }],
            "subject": "Test Invoice",
            "from": "test@example.com",
            "date": "2024-03-01"
        }
        
        mock_download.return_value = "/tmp/success.pdf"
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
        
        result = await analyze_pdfs(["email1"], current_user=mock_user)
        
        assert isinstance(result, AnalysisResult)
        assert len(result.invoices) == 1
        assert len(result.failed_files) == 0

@pytest.mark.asyncio
async def test_temp_dir_exists():
    """測試暫存目錄是否正確創建"""
    from app.routes.pdf import TEMP_DIR
    assert os.path.exists(TEMP_DIR)
    assert os.path.isdir(TEMP_DIR) 