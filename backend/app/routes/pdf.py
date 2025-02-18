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
        logger.info(f"開始下載附件: message_id={message_id}, filename={attachment['filename']}, provider={email_service.provider}")
        logger.info(f"附件詳細資訊: {attachment}")
        
        # 確保檔案名稱安全且唯一
        safe_filename = "".join(c for c in attachment['filename'] if c.isalnum() or c in "._- ")
        unique_filename = f"{uuid.uuid4()}_{safe_filename}"
        file_path = os.path.join(temp_dir, unique_filename)
        logger.info(f"目標檔案路徑: {file_path}")
        
        if not attachment.get('attachmentId'):
            logger.error(f"附件缺少 attachmentId: {attachment}")
            return None

        # 根據不同的郵件服務提供者使用不同的下載邏輯
        if email_service.provider.upper() == "MICROSOFT":
            # Microsoft Graph API 下載邏輯
            content_url = f"{email_service.base_url}/messages/{message_id}/attachments/{attachment['attachmentId']}/$value"
            logger.info(f"Microsoft 下載 URL: {content_url}")
            
            response = await client.get(
                content_url,
                headers={
                    "Authorization": f"Bearer {email_service.access_token}",
                    "Accept": "application/json"
                }
            )
            logger.info(f"Microsoft 回應狀態: {response.status_code}")
            logger.info(f"Microsoft 回應標頭: {dict(response.headers)}")
            
            if response.status_code != 200:
                logger.error(f"Microsoft 附件下載失敗: HTTP {response.status_code}")
                logger.error(f"錯誤回應: {response.text}")
                return None
                
            # 直接寫入二進位內容
            content = response.content
            logger.info(f"取得內容大小: {len(content)} bytes")
            
        else:  # Gmail
            # Gmail API 下載邏輯
            url = f"{email_service.base_url}/messages/{message_id}/attachments/{attachment['attachmentId']}"
            logger.info(f"Gmail 下載 URL: {url}")
            
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {email_service.access_token}"}
            )
            logger.info(f"Gmail 回應狀態: {response.status_code}")
            logger.info(f"Gmail 回應標頭: {dict(response.headers)}")
            
            if response.status_code != 200:
                logger.error(f"Gmail 附件下載失敗: HTTP {response.status_code}")
                logger.error(f"錯誤回應: {response.text}")
                return None
                
            # 解碼 base64 內容
            attachment_data = response.json()
            logger.info(f"Gmail 回應資料鍵值: {attachment_data.keys()}")
            
            if 'data' not in attachment_data:
                logger.error("Gmail 附件資料缺少 data 欄位")
                return None
                
            try:
                content = base64.urlsafe_b64decode(attachment_data['data'])
                logger.info(f"Base64 解碼後內容大小: {len(content)} bytes")
            except Exception as e:
                logger.error(f"Base64 解碼失敗: {str(e)}")
                return None

        # 確保目標目錄存在且有寫入權限
        os.makedirs(temp_dir, exist_ok=True)
        logger.info(f"確認目標目錄: {temp_dir}")
        logger.info(f"目錄權限: {oct(os.stat(temp_dir).st_mode)[-3:]}")
        
        # 寫入檔案
        try:
            with open(file_path, 'wb') as f:
                f.write(content)
            logger.info(f"檔案寫入完成: {file_path}")
        except IOError as e:
            logger.error(f"檔案寫入失敗: {str(e)}")
            return None

        # 驗證檔案
        if not os.path.exists(file_path):
            logger.error("檔案未成功建立")
            return None
            
        file_size = os.path.getsize(file_path)
        logger.info(f"檔案大小: {file_size} bytes")
        
        if file_size == 0:
            logger.error("檔案大小為 0")
            os.remove(file_path)
            return None
            
        # 設定檔案權限
        os.chmod(file_path, 0o644)
        logger.info(f"設定檔案權限: 644")
        
        logger.info(f"檔案已成功下載並儲存: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"下載附件時發生錯誤: {str(e)}")
        logger.exception("完整錯誤堆疊:")
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
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
            
            # 更新正則表達式以匹配中文格式
            patterns = {
                "invoice_number": r"(?:發票號碼[\s]*|^)([A-Z]{2}[0-9]{8})",  # 修改發票號碼匹配模式
                "invoice_date": r"(?:發票日期|[A-Z]{2}[0-9]{8})\s+(\d{4}/\d{2}/\d{2})",  # 修改日期匹配模式，直接匹配日期格式
                "buyer_name": r"買受人\s*([^\s]+)",
                "buyer_tax_id": r"買受人統一編號\s*([^\s]+)",
                "seller_name": r"\d+\s*(.+公司[^(\n\r)]*)",  # 簡化公司名稱匹配
                "taxable_amount": r"應稅銷售額\s*(\d+)",
                "tax_free_amount": r"免稅銷售額\s*(\d+)",
                "zero_tax_amount": r"零稅率銷售額\s*(\d+)",
                "tax_amount": r"營業稅稅額\s*(\d+)",
                "total_amount": r"發票總金額\s*(\d+)"
            }
            
            result = {}
            for key, pattern in patterns.items():
                match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)  # 添加 IGNORECASE 標誌
                if match:
                    value = match.group(1).strip()
                    if key in ["taxable_amount", "tax_free_amount", "zero_tax_amount", "tax_amount", "total_amount"]:
                        result[key] = float(value)
                    else:
                        result[key] = value
                    logger.info(f"找到 {key}: {value}")  # 添加更詳細的日誌
                else:
                    logger.info(f"未找到 {key}")  # 記錄未找到的欄位
            
            # 如果找到必要欄位
            if all(key in result for key in ["invoice_number", "total_amount"]):
                # 添加郵件資訊
                result.update({
                    "email_subject": email_info.get("subject", ""),
                    "email_sender": email_info.get("from", ""),
                    "email_date": email_info.get("date", "")
                })
                logger.info(f"成功提取發票資料: {result}")
                return result
            
            logger.error(f"無法從文字中提取發票資訊，缺少必要欄位。已找到的欄位: {list(result.keys())}")
            logger.error(f"未找到的欄位: {[key for key in ['invoice_number', 'total_amount'] if key not in result]}")
            # 輸出完整的文字內容，以便調試
            logger.error(f"完整文字內容:\n{text}")
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
        
        # 創建一個異步 HTTP 客戶端
        async with httpx.AsyncClient() as client:
            for email_id in emails:
                try:
                    try:
                        email_details = await email_service.get_email_details(email_id)
                        logger.info(f"成功獲取郵件詳細資訊: {email_id}")
                    except HTTPException as he:
                        raise he
                    except Exception as e:
                        logger.error(f"獲取郵件 {email_id} 詳細資訊失敗: {str(e)}")
                        result.failed_files.append(f"郵件 {email_id} 無法取得詳細資訊")
                        current_progress.current += 1
                        continue
                    
                    if not email_details or "attachments" not in email_details:
                        logger.error(f"郵件 {email_id} 缺少附件資訊")
                        result.failed_files.append(f"郵件 {email_id} 無法取得詳細資訊")
                        current_progress.current += 1
                        continue
                    
                    # 處理附件
                    for attachment in email_details["attachments"]:
                        logger.info(f"處理附件: {attachment.get('filename')} (MIME類型: {attachment.get('mimeType')})")
                        
                        # 檢查是否為 PDF 檔案（擴充支援的 MIME 類型）
                        is_pdf = (
                            attachment["mimeType"] in ["application/pdf", "application/octet-stream"] and
                            attachment["filename"].lower().endswith(".pdf")
                        )
                        
                        if is_pdf:
                            logger.info(f"開始下載 PDF 附件: {attachment['filename']}")
                            pdf_path = await download_pdf_attachment(
                                client,  # 使用創建的 client
                                email_service,
                                email_id,
                                attachment,
                                TEMP_DIR
                            )
                            
                            if pdf_path:
                                logger.info(f"PDF 下載成功，路徑: {pdf_path}")
                                invoice_data = extract_invoice_data(pdf_path, email_details)
                                if invoice_data:
                                    logger.info(f"成功解析發票資料: {attachment['filename']}")
                                    result.invoices.append(invoice_data)
                                else:
                                    logger.error(f"無法解析發票資料: {attachment['filename']}")
                                    result.failed_files.append(attachment["filename"])
                            else:
                                logger.error(f"PDF 下載失敗: {attachment['filename']}")
                                result.failed_files.append(f"下載失敗: {attachment['filename']}")
                        else:
                            logger.info(f"跳過非 PDF 附件: {attachment['filename']}")
                    
                except HTTPException as he:
                    raise he
                except Exception as e:
                    logger.error(f"處理郵件 {email_id} 時發生錯誤: {str(e)}")
                    result.failed_files.append(f"郵件 {email_id}: {str(e)}")
                
                current_progress.current += 1
                current_progress.message = f"已處理 {current_progress.current}/{current_progress.total} 封郵件"
            
            current_progress.status = "completed"
            current_progress.message = "處理完成"
            return result
            
    except HTTPException as he:
        current_progress.status = "error"
        current_progress.message = str(he.detail)
        raise he
    except Exception as e:
        current_progress.status = "error"
        current_progress.message = str(e)
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