from fastapi import APIRouter, HTTPException, Depends
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
from app.routes.auth import get_current_user
from app.services.email import EmailService
import asyncio
import httpx
import pdfplumber
import re
import uuid
import base64

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["pdf"])

# 建立暫存目錄
TEMP_DIR = os.path.join(tempfile.gettempdir(), "pdf-invoice-manager")
os.makedirs(TEMP_DIR, exist_ok=True)

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

async def download_pdf_attachment(client: httpx.AsyncClient, email_service: EmailService, message_id: str, attachment: Dict[str, Any], temp_dir: str) -> Optional[str]:
    """下載 PDF 附件"""
    try:
        logger.info(f"開始下載附件: message_id={message_id}, filename={attachment['filename']}")
        logger.info(f"附件詳細資訊: {attachment}")
        
        # 確保檔名安全
        safe_filename = "".join(c for c in attachment['filename'] if c.isalnum() or c in "._- ")
        file_path = os.path.join(temp_dir, safe_filename)
        
        if not attachment.get('attachmentId'):
            logger.error(f"附件缺少 attachmentId: {attachment}")
            return None
            
        logger.info(f"準備下載附件到: {file_path}")
        
        if email_service.provider == "GOOGLE":
            url = f"{email_service.base_url}/messages/{message_id}/attachments/{attachment['attachmentId']}"
            logger.info(f"使用 Gmail API 下載附件: {url}")
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {email_service.access_token}"}
            )
        else:
            url = f"{email_service.base_url}/messages/{message_id}/attachments/{attachment['attachmentId']}"
            logger.info(f"使用 Microsoft Graph API 下載附件: {url}")
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {email_service.access_token}"}
            )

        if response.status_code != 200:
            logger.error(f"下載附件失敗: HTTP {response.status_code} - {response.text}")
            return None
            
        logger.info(f"成功獲取附件資料，開始解碼")

        # 儲存檔案
        try:
            with open(file_path, 'wb') as f:
                if email_service.provider == "GOOGLE":
                    attachment_data = response.json()
                    logger.info(f"Gmail 附件資料: {attachment_data.keys()}")
                    if 'data' not in attachment_data:
                        logger.error(f"Gmail 附件資料缺少 data 欄位: {attachment_data}")
                        return None
                    decoded_data = base64.urlsafe_b64decode(attachment_data['data'])
                    f.write(decoded_data)
                else:
                    f.write(response.content)
                    
            logger.info(f"檔案已儲存: {file_path}")
            
            # 驗證檔案
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                logger.info(f"檔案大小: {file_size} bytes")
                if file_size == 0:
                    logger.error("檔案大小為 0")
                    os.remove(file_path)
                    return None
                return file_path
            else:
                logger.error("檔案未成功建立")
                return None
                
        except Exception as e:
            logger.error(f"寫入檔案時發生錯誤: {str(e)}")
            if os.path.exists(file_path):
                os.remove(file_path)
            return None
            
    except Exception as e:
        logger.error(f"下載附件時發生錯誤: {str(e)}")
        logger.exception("完整錯誤堆疊:")
        return None

def extract_invoice_data(pdf_path: str, email_info: Dict[str, Any]) -> Optional[InvoiceData]:
    """從 PDF 提取發票資訊"""
    try:
        logger.info(f"開始解析 PDF: {pdf_path}")
        logger.info(f"Email 資訊: {email_info}")
        
        if not os.path.exists(pdf_path):
            logger.error(f"PDF 檔案不存在: {pdf_path}")
            return None
            
        file_size = os.path.getsize(pdf_path)
        logger.info(f"PDF 檔案大小: {file_size} bytes")
        
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"PDF 頁數: {len(pdf.pages)}")
            text = ""
            items = []
            invoice_data = {
                'invoice_number': '',
                'invoice_date': '',
                'buyer_name': '',
                'buyer_tax_id': '',
                'seller_name': '',
                'taxable_amount': 0.0,
                'tax_free_amount': 0.0,
                'zero_tax_amount': 0.0,
                'tax_amount': 0.0,
                'total_amount': 0.0
            }

            # 提取每頁文字
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                logger.info(f"第 {page_num} 頁文字長度: {len(page_text) if page_text else 0}")
                if page_text:
                    text += page_text + "\n"

            logger.info(f"提取的完整文本: {text}")

            # 使用多個正則表達式模式嘗試匹配
            patterns = {
                'invoice_number': [
                    r'發票號碼[:\s]+(\w+)',
                    r'發票編號[:\s]+(\w+)',
                    r'NO[.\s]+(\w+)',
                    r'[發票號碼編號]\s*[:：]?\s*(\w+)',
                ],
                'invoice_date': [
                    r'發票日期[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                    r'日期[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                    r'Date[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                ],
                'buyer_name': [
                    r'買受人[:\s]+(.+?)(?=[\n統])',
                    r'公司名稱[:\s]+(.+?)(?=[\n統])',
                    r'Customer[:\s]+(.+?)(?=[\n統])',
                ],
                'buyer_tax_id': [
                    r'統一編號[:\s]+(\d{8})',
                    r'統編[:\s]+(\d{8})',
                    r'Tax ID[:\s]+(\d{8})',
                ],
                'seller_name': [
                    r'賣方名稱[:\s]+(.+?)(?=[\n統])',
                    r'賣方[:\s]+(.+?)(?=[\n統])',
                    r'Seller[:\s]+(.+?)(?=[\n統])',
                ],
                'taxable_amount': [
                    r'應稅銷售額[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                    r'銷售額[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                    r'小計[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                ],
                'tax_amount': [
                    r'營業稅稅額[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                    r'稅額[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                    r'Tax[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                ],
                'total_amount': [
                    r'發票總金額[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                    r'總計[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                    r'Total[:\s]*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                ]
            }

            # 提取每個欄位的資訊
            for key, pattern_list in patterns.items():
                for pattern in pattern_list:
                    logger.info(f"嘗試匹配 {key} 使用模式: {pattern}")
                    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                    if match:
                        value = match.group(1).strip().replace(',', '')
                        logger.info(f"找到 {key}: {value}")
                        
                        # 處理數值型欄位
                        if key in ['taxable_amount', 'tax_amount', 'total_amount']:
                            try:
                                invoice_data[key] = float(value)
                            except ValueError:
                                logger.error(f"轉換 {key} 為數值時失敗: {value}")
                                continue
                        else:
                            invoice_data[key] = value
                        break
                    else:
                        logger.debug(f"使用模式 {pattern} 未找到 {key} 的匹配")

            # 解析商品項目（使用多個模式）
            item_patterns = [
                r"(.+?)\s+(應稅|免稅|零稅率)\s+(\d+)\s+(\d+)\s+(\d+)",
                r"(.+?)\s+(\d+)\s+(\d+)\s+(\d+)",  # 簡化版本，不含稅別
                r"(.+?)\s+數量[:\s]*(\d+)\s+單價[:\s]*(\d+)\s+金額[:\s]*(\d+)",  # 帶標籤版本
            ]

            lines = text.split('\n')
            logger.info(f"開始解析商品項目，總行數: {len(lines)}")
            
            for line_num, line in enumerate(lines, 1):
                logger.debug(f"處理第 {line_num} 行: {line}")
                
                for pattern in item_patterns:
                    match = re.search(pattern, line.strip())
                    if match:
                        try:
                            groups = match.groups()
                            if len(groups) == 5:  # 完整版本（含稅別）
                                item = {
                                    "品名": groups[0].strip(),
                                    "稅別": groups[1],
                                    "數量": int(groups[2]),
                                    "單價": float(groups[3]),
                                    "金額": float(groups[4])
                                }
                            else:  # 簡化版本
                                item = {
                                    "品名": groups[0].strip(),
                                    "稅別": "應稅",  # 預設應稅
                                    "數量": int(groups[1]),
                                    "單價": float(groups[2]),
                                    "金額": float(groups[3])
                                }
                            
                            items.append(item)
                            logger.info(f"找到商品項目: {item}")

                            # 根據稅別更新對應金額
                            if item["稅別"] == "應稅":
                                invoice_data["taxable_amount"] += item["金額"]
                            elif item["稅別"] == "免稅":
                                invoice_data["tax_free_amount"] += item["金額"]
                            elif item["稅別"] == "零稅率":
                                invoice_data["zero_tax_amount"] += item["金額"]
                            
                            break  # 找到匹配就跳出內部循環
                            
                        except (ValueError, IndexError) as e:
                            logger.error(f"解析商品項目時發生錯誤: {str(e)}, 行內容: {line}")
                            continue

            # 如果沒有找到發票號碼，嘗試從檔名獲取
            if not invoice_data['invoice_number']:
                filename = os.path.basename(pdf_path)
                number_match = re.search(r'[A-Z]{2}\d{8}', filename)
                if number_match:
                    invoice_data['invoice_number'] = number_match.group(0)
                    logger.info(f"從檔名提取發票號碼: {invoice_data['invoice_number']}")

            # 檢查必要欄位並設置預設值
            if not invoice_data['invoice_number']:
                logger.error("未找到發票號碼")
                return None

            if not invoice_data['invoice_date']:
                invoice_data['invoice_date'] = email_info.get('date', '')[:10]
                logger.info(f"使用郵件日期作為發票日期: {invoice_data['invoice_date']}")

            logger.info(f"PDF 解析完成，發票資料: {invoice_data}")
            logger.info(f"商品項目數量: {len(items)}")

            # 建立回傳物件
            try:
                result = InvoiceData(
                    email_subject=email_info['subject'],
                    email_sender=email_info['from'],
                    email_date=email_info['date'],
                    **invoice_data
                )
                logger.info(f"成功建立 InvoiceData 物件: {result}")
                return result
            except Exception as e:
                logger.error(f"建立 InvoiceData 物件失敗: {str(e)}")
                return None
                
    except Exception as e:
        logger.error(f"解析 PDF 時發生錯誤: {str(e)}")
        logger.exception("完整錯誤堆疊:")
        return None

@router.post("/pdf/analyze")
async def analyze_pdfs(
    email_ids: List[str],
    access_token: str = Depends(get_current_user)
) -> AnalysisResult:
    """分析 PDF 檔案"""
    global current_progress
    
    try:
        logger.info(f"開始分析 PDF，郵件數量: {len(email_ids)}")
        
        # 建立批次專用的暫存目錄
        batch_id = str(uuid.uuid4())
        batch_temp_dir = os.path.join(TEMP_DIR, batch_id)
        os.makedirs(batch_temp_dir, exist_ok=True)
        
        logger.info(f"建立暫存目錄: {batch_temp_dir}")
        
        # 初始化進度
        current_progress = AnalysisProgress(
            total=len(email_ids),
            current=0,
            status="processing",
            message="開始下載 PDF 檔案"
        )
        
        # 初始化 email service
        email_service = EmailService(access_token)
        logger.info(f"初始化 EmailService，提供者: {email_service.provider}")
        
        invoices = []
        failed_files = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for email_id in email_ids:
                try:
                    logger.info(f"處理郵件 {email_id}")
                    
                    # 獲取郵件詳細信息
                    email_details = await email_service.get_email_details(email_id)
                    if not email_details:
                        logger.error(f"無法獲取郵件詳細信息: {email_id}")
                        failed_files.append(f"無法獲取郵件詳細信息: {email_id}")
                        continue
                    
                    logger.info(f"郵件詳細信息: {email_details}")
                    
                    # 檢查附件
                    if not email_details.get("attachments"):
                        logger.warning(f"郵件 {email_id} 沒有附件")
                        failed_files.append(f"沒有附件: {email_details.get('subject', '無主旨')}")
                        continue
                        
                    # 下載 PDF 附件
                    pdf_found = False
                    for attachment in email_details["attachments"]:
                        # 檢查 MIME 類型或檔案副檔名
                        is_pdf = (
                            attachment["mimeType"] == "application/pdf" or
                            attachment["filename"].lower().endswith('.pdf')
                        )
                        
                        if is_pdf:
                            pdf_found = True
                            logger.info(f"發現 PDF 附件: {attachment['filename']}")
                            
                            pdf_path = await download_pdf_attachment(
                                client,
                                email_service,
                                email_id,
                                attachment,
                                batch_temp_dir
                            )
                            
                            if pdf_path:
                                logger.info(f"成功下載 PDF: {pdf_path}")
                                # 解析 PDF
                                invoice_data = extract_invoice_data(pdf_path, email_details)
                                if invoice_data:
                                    logger.info(f"成功解析發票資料: {invoice_data}")
                                    invoices.append(invoice_data)
                                else:
                                    logger.error(f"無法解析 PDF: {pdf_path}")
                                    failed_files.append(f"無法解析: {attachment['filename']}")
                            else:
                                logger.error(f"無法下載 PDF: {attachment['filename']}")
                                failed_files.append(f"無法下載: {attachment['filename']}")
                    
                    if not pdf_found:
                        logger.warning(f"郵件 {email_id} 沒有 PDF 附件")
                        failed_files.append(f"沒有 PDF 附件: {email_details.get('subject', '無主旨')}")
                    
                    current_progress.current += 1
                    current_progress.message = f"已處理 {current_progress.current}/{current_progress.total} 封郵件"
                    
                except Exception as e:
                    logger.error(f"處理郵件 {email_id} 時發生錯誤: {str(e)}")
                    logger.exception("完整錯誤堆疊:")
                    failed_files.append(f"處理失敗: {email_id}")
                    continue
        
        # 建立 ZIP 檔案
        zip_path = os.path.join(TEMP_DIR, f"{batch_id}.zip")
        logger.info(f"開始建立 ZIP 檔案: {zip_path}")
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, _, files in os.walk(batch_temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, batch_temp_dir)
                    zipf.write(file_path, arcname)
                    logger.info(f"添加檔案到 ZIP: {arcname}")
        
        # 更新進度
        current_progress.status = "completed"
        current_progress.message = "處理完成"
        
        logger.info(f"分析完成，成功解析 {len(invoices)} 個發票，失敗 {len(failed_files)} 個檔案")
        
        return AnalysisResult(
            invoices=invoices,
            failed_files=failed_files,
            download_url=f"/api/pdf/download/{batch_id}"
        )
        
    except Exception as e:
        logger.error(f"PDF 分析過程發生錯誤: {str(e)}")
        logger.exception("完整錯誤堆疊:")
        current_progress.status = "error"
        current_progress.message = str(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pdf/progress")
async def get_analysis_progress() -> AnalysisProgress:
    """獲取分析進度"""
    return current_progress

@router.get("/pdf/download/{batch_id}")
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
@router.on_event("startup")
async def start_cleanup_task():
    asyncio.create_task(cleanup_temp_files()) 