from fastapi import APIRouter, HTTPException, Depends, FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import zipfile
import tempfile
import os
import shutil
from pathlib import Path
from app.models.user import User
from app.routes.auth import get_current_user
from app.services.email import EmailService
import asyncio
import httpx
import pdfplumber
import re
import uuid
import base64
from contextlib import asynccontextmanager

# 設定日誌
logger = logging.getLogger(__name__)

router = APIRouter(tags=["pdf"])

# 建立暫存目錄
TEMP_DIR = os.path.join(tempfile.gettempdir(), "pdf-invoice-manager")
os.makedirs(TEMP_DIR, exist_ok=True)

# 定義資料模型
class InvoiceData(BaseModel):
    email_subject: str
    email_sender: str
    email_date: str
    invoice_number: str
    invoice_date: str
    buyer_name: str
    buyer_tax_id: str
    seller_name: str
    taxable_amount: float
    tax_free_amount: float
    zero_tax_amount: float
    tax_amount: float
    total_amount: float

class AnalysisProgress(BaseModel):
    total: int
    current: int
    status: str
    message: str

class AnalysisResult(BaseModel):
    invoices: List[InvoiceData]
    failed_files: List[str]
    download_url: Optional[str] = None

# 全局變數用於追蹤進度
current_progress = AnalysisProgress(total=0, current=0, status="idle", message="")

# 新增一個請求模型，以符合前端傳入的 JSON 格式
class AnalyzeRequest(BaseModel):
    emails: List[str]

async def download_pdf_attachment(client: httpx.AsyncClient, email_service: EmailService, message_id: str, attachment: Dict[str, Any], temp_dir: str) -> Optional[str]:
    """下載 PDF 附件"""
    try:
        logger.info(f"開始下載附件: message_id={message_id}, filename={attachment['filename']}")
        safe_filename = "".join(c for c in attachment['filename'] if c.isalnum() or c in "._- ")
        file_path = os.path.join(temp_dir, safe_filename)
        
        if not attachment.get('attachmentId'):
            logger.error(f"附件缺少 attachmentId: {attachment}")
            return None

        # Microsoft Graph API 專用處理
        if email_service.provider == "MICROSOFT":
            try:
                # 1. 先取得附件資訊
                info_url = f"{email_service.base_url}/messages/{message_id}/attachments/{attachment['attachmentId']}"
                info_response = await client.get(
                    info_url,
                    headers={"Authorization": f"Bearer {email_service.access_token}"}
                )
                
                if info_response.status_code != 200:
                    logger.error(f"獲取附件資訊失敗: {info_response.status_code}")
                    return None
                
                # 2. 下載附件內容
                content_url = f"{info_url}/$value"
                content_response = await client.get(
                    content_url,
                    headers={
                        "Authorization": f"Bearer {email_service.access_token}",
                        "Accept": "application/json"
                    }
                )
                
                if content_response.status_code != 200:
                    logger.error(f"下載附件內容失敗: {content_response.status_code}")
                    return None
                
                # 寫入檔案
                with open(file_path, 'wb') as f:
                    f.write(content_response.content)
                
            except Exception as e:
                logger.error(f"Microsoft 附件下載失敗: {str(e)}")
                return None
                
        else:  # Google 處理邏輯保持不變
            # 根據不同提供者調整 URL
            if email_service.provider == "GOOGLE":
                url = f"{email_service.base_url}/messages/{message_id}/attachments/{attachment['attachmentId']}"
            else:  # MICROSOFT
                # 需加上 /$value 以獲取附件原始二進位內容
                url = f"{email_service.base_url}/messages/{message_id}/attachments/{attachment['attachmentId']}/$value"
            
            logger.info(f"準備下載附件至: {file_path}，使用 URL: {url}")
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {email_service.access_token}"}
            )

            if response.status_code != 200:
                logger.error(f"下載附件失敗: HTTP {response.status_code} - {response.text}")
                return None

            # 儲存檔案
            with open(file_path, 'wb') as f:
                if email_service.provider == "GOOGLE":
                    attachment_data = response.json()
                    if 'data' not in attachment_data:
                        logger.error(f"Gmail 附件資料缺少 data 欄位: {attachment_data}")
                        return None
                    decoded_data = base64.urlsafe_b64decode(attachment_data['data'])
                    f.write(decoded_data)
                else:
                    # 直接寫入原始二進位資料
                    f.write(response.content)

        logger.info(f"檔案已儲存: {file_path}")
        # 驗證檔案尺寸或其他檢查
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path
        else:
            logger.error("檔案未成功儲存或大小為 0")
            return None

    except Exception as e:
        logger.error(f"下載附件時發生錯誤: {str(e)}")
        logger.exception("完整錯誤堆疊:")
        return None

def extract_invoice_data(pdf_path: str, email_info: dict) -> Optional[Dict[str, Any]]:
    """從 PDF 提取發票資料"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            logger.info(f"提取的文字內容:\n{text}")
            
            # 更新正則表達式以匹配英文標籤
            patterns = {
                "invoice_number": r"Invoice Number:\s*([A-Z0-9-]+)",
                "invoice_date": r"Invoice Date:\s*(\d{4}-\d{2}-\d{2})",
                "buyer_name": r"Buyer Name:\s*([^\n]+)",
                "buyer_tax_id": r"Buyer Tax ID:\s*(\d{8})",
                "seller_name": r"Seller Name:\s*([^\n]+)",
                "taxable_amount": r"Taxable Amount:\s*(\d+)",
                "tax_free_amount": r"Tax Free Amount:\s*(\d+)",
                "zero_tax_amount": r"Zero Tax Amount:\s*(\d+)",
                "tax_amount": r"Tax Amount:\s*(\d+)",
                "total_amount": r"Total Amount:\s*(\d+)"
            }
            
            result = {}
            for key, pattern in patterns.items():
                match = re.search(pattern, text)  # 移除 re.IGNORECASE
                if match:
                    value = match.group(1).strip()
                    if key in ["taxable_amount", "tax_free_amount", "zero_tax_amount", "tax_amount", "total_amount"]:
                        result[key] = float(value)
                    else:
                        result[key] = value
            
            # 如果找到必要欄位
            if all(key in result for key in ["invoice_number", "total_amount"]):
                # 添加郵件資訊
                result.update({
                    "email_subject": email_info.get("subject", ""),
                    "email_sender": email_info.get("from", ""),
                    "email_date": email_info.get("date", "")
                })
                return result
            
            logger.error(f"無法從文字中提取發票資訊:\n{text}")
            return None
            
    except Exception as e:
        logger.error(f"解析 PDF 時發生錯誤: {str(e)}")
        logger.exception("完整錯誤堆疊:")
        return None

# 建議加入的錯誤處理裝飾器
def handle_pdf_errors(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"PDF 處理失敗: {str(e)}")
            if "Invalid Credentials" in str(e):
                raise HTTPException(status_code=401, detail="認證失敗")
            elif "Permission Denied" in str(e):
                raise HTTPException(status_code=403, detail="權限不足")
            elif "PDF parsing error" in str(e):
                raise HTTPException(status_code=400, detail="PDF 解析失敗")
            else:
                raise HTTPException(status_code=500, detail=f"系統錯誤: {str(e)}")
    return wrapper

@router.post("/analyze")
async def analyze_pdfs(
    payload: AnalyzeRequest,
    current_user: User = Depends(get_current_user)
) -> AnalysisResult:
    # 從請求模型中提取出 emails 列表
    emails = payload.emails

    # 移除多餘的型別檢查，直接使用 get_current_user 注入的 User 物件
    
    global current_progress
    current_progress = AnalysisProgress(
        total=len(emails),
        current=0,
        status="processing",
        message="開始處理"
    )
    
    result = AnalysisResult(
        invoices=[],
        failed_files=[],
        download_url=None
    )
    
    try:
        email_service = EmailService(current_user.access_token, current_user.provider)
        
        for email_id in emails:
            try:
                try:
                    email_details = await email_service.get_email_details(email_id)
                except HTTPException as he:
                    raise he
                except Exception as e:
                    logger.error(f"獲取郵件 {email_id} 詳細資訊失敗: {str(e)}")
                    result.failed_files.append(f"郵件 {email_id} 無法取得詳細資訊")
                    current_progress.current += 1
                    continue
                
                if not email_details or "attachments" not in email_details:
                    result.failed_files.append(f"郵件 {email_id} 無法取得詳細資訊")
                    current_progress.current += 1
                    continue
                
                # 處理附件
                for attachment in email_details["attachments"]:
                    if attachment["mimeType"] == "application/pdf":
                        pdf_path = await download_pdf_attachment(
                            email_service.client,
                            email_service,
                            email_id,
                            attachment,
                            TEMP_DIR
                        )
                        
                        if pdf_path:
                            invoice_data = extract_invoice_data(pdf_path, email_details)
                            if invoice_data:
                                result.invoices.append(invoice_data)
                            else:
                                result.failed_files.append(attachment["filename"])
            except HTTPException as he:
                raise he
            except Exception as e:
                logger.error(f"處理郵件 {email_id} 時發生錯誤: {str(e)}")
                result.failed_files.append(f"郵件 {email_id}: {str(e)}")
            
            current_progress.current += 1
        
        return result
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"郵件服務錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"郵件服務錯誤: {str(e)}")

@router.get("/progress")
async def get_analysis_progress() -> AnalysisProgress:
    """獲取分析進度"""
    return current_progress

@router.get("/download/{batch_id}")
async def download_pdfs(batch_id: str):
    """下載 PDF 檔案"""
    try:
        zip_path = os.path.join(TEMP_DIR, f"{batch_id}.zip")
        if not os.path.exists(zip_path):
            raise HTTPException(status_code=404, detail="檔案不存在")
            
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"invoices_{batch_id}.zip"
        )
    except Exception as e:
        logger.error(f"下載 PDF 時發生錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 定期清理暫存檔案
async def cleanup_temp_files():
    """清理超過 24 小時的暫存檔案"""
    while True:
        try:
            current_time = datetime.now().timestamp()
            for item in os.listdir(TEMP_DIR):
                item_path = os.path.join(TEMP_DIR, item)
                if os.path.getctime(item_path) < current_time - 86400:  # 24 小時
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
        except Exception as e:
            logger.error(f"清理暫存檔案時發生錯誤: {str(e)}")
        await asyncio.sleep(3600)  # 每小時執行一次

# 啟動清理任務
@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(cleanup_temp_files())
    yield
    cleanup_task.cancel() 