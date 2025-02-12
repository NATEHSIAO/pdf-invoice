import io
import logging
import base64
from typing import List, Dict
from .email_adapter import EmailAdapter, GmailAdapter, MicrosoftAdapter
import pdfplumber

logger = logging.getLogger(__name__)


def standardize_attachment(attachment: dict) -> bytes:
    """轉換附件資料為標準的 PDF 二進位內容"""
    try:
        # 檢查是否有直接的內容（Microsoft 格式）
        if "content" in attachment:
            logger.info("使用 Microsoft 格式處理附件")
            return base64.b64decode(attachment["content"])
        
        # 檢查是否有 data 欄位（Gmail 格式）
        elif "data" in attachment:
            logger.info("使用 Gmail 格式處理附件")
            return base64.urlsafe_b64decode(attachment["data"].encode('utf-8'))
        
        logger.error(f"不支援的附件格式: {attachment.keys()}")
        raise ValueError('附件數據不存在或格式不支援')
    except Exception as e:
        logger.error(f"處理附件標準化失敗: {e}")
        raise


def process_pdf_attachment(pdf_data: bytes) -> Dict:
    """使用 pdfplumber 解析 PDF 並返回發票資料"""
    invoice_data = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            if not pdf.pages:
                logger.warning("PDF 無內容頁")
                return invoice_data
                
            # 取得第一頁文字
            page = pdf.pages[0]
            text = page.extract_text()
            
            if not text:
                logger.warning("無法提取 PDF 文字內容")
                return invoice_data
                
            # 解析發票欄位（這裡需要根據實際發票格式調整）
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                # 發票號碼
                if "發票號碼" in line:
                    invoice_data["invoice_number"] = line.split("：")[-1].strip()
                # 發票日期
                elif "發票日期" in line:
                    invoice_data["invoice_date"] = line.split("：")[-1].strip()
                # 買受人
                elif "買受人" in line:
                    invoice_data["buyer_name"] = line.split("：")[-1].strip()
                # 統一編號
                elif "統一編號" in line:
                    invoice_data["tax_id"] = line.split("：")[-1].strip()
                # 金額相關
                elif "金額" in line:
                    try:
                        amount = float(line.split("：")[-1].replace(",", "").strip())
                        if "總" in line:
                            invoice_data["total_amount"] = amount
                        elif "稅額" in line:
                            invoice_data["tax_amount"] = amount
                    except ValueError:
                        logger.warning(f"無法解析金額: {line}")
            
            logger.info(f"解析出的發票資料: {invoice_data}")
            return invoice_data
            
    except Exception as e:
        logger.error(f"PDF 解析失敗: {e}")
        raise


async def process_email_attachments(email_id: str, provider: str, access_token: str) -> List[Dict]:
    """根據 email_id 與提供者，選擇相對應的 Adapter 下載並處理附件，返回發票資料列表"""
    try:
        provider = provider.lower()
        logger.info(f"開始處理郵件附件，提供者: {provider}, email_id: {email_id}")

        # 檢查郵件 ID 格式以驗證提供者
        if 'AQMK' in email_id:  # Microsoft 郵件 ID 特徵
            logger.info("檢測到 Microsoft 格式的郵件 ID")
            adapter = MicrosoftAdapter(access_token)
        elif any(x in provider for x in ['gmail', 'google']):
            logger.info("使用 Gmail 適配器")
            adapter = GmailAdapter(access_token)
        else:
            logger.error(f"無法識別的郵件提供者: {provider}, email_id: {email_id}")
            return []

        logger.info(f"開始獲取 PDF 附件: email_id={email_id}, provider={provider}")
        attachments = await adapter.get_pdf_attachments(email_id)
        
        if not attachments:
            logger.warning(f"未找到 PDF 附件: email_id={email_id}")
            return []
            
        results = []
        for att in attachments:
            try:
                logger.info(f"處理附件: {att.get('filename') or att.get('name', '未知檔名')}")
                pdf_data = standardize_attachment(att)
                invoice_data = process_pdf_attachment(pdf_data)
                if invoice_data:  # 只添加成功解析的結果
                    results.append(invoice_data)
                else:
                    logger.warning(f"無法從 PDF 提取發票資料: {att.get('filename') or att.get('name', '未知檔名')}")
            except Exception as e:
                logger.error(f"處理 email_id {email_id} 附件失敗: {str(e)}")
                continue
                
        return results
        
    except Exception as e:
        logger.error(f"處理郵件附件時發生錯誤: {str(e)}")
        return [] 