import io
import logging
import base64
from typing import List, Dict
import pdfplumber
from .email_adapter import EmailAdapter, GmailAdapter, MicrosoftAdapter

logger = logging.getLogger(__name__)


def standardize_attachment(attachment: dict) -> bytes:
    """
    轉換附件資料為標準的 PDF 二進位內容

    根據不同提供者的 API 格式：
    - Microsoft Graph API 提供的附件中，PDF 內容存在 "content" 欄位（使用標準 base64 編碼）
    - Gmail API 提供的附件中，PDF 內容存在 "data" 欄位（使用 URL-safe base64 編碼）
    """
    try:
        if "content" in attachment:
            logger.info("使用 Microsoft 格式處理附件")
            return base64.b64decode(attachment["content"])
        elif "data" in attachment:
            logger.info("使用 Gmail 格式處理附件")
            return base64.urlsafe_b64decode(attachment["data"].encode("utf-8"))
        else:
            logger.error(f"不支援的附件格式: {attachment.keys()}")
            raise ValueError("附件數據不存在或格式不支援")
    except Exception as e:
        logger.error(f"處理附件標準化失敗: {e}")
        raise


def process_pdf_attachment(pdf_data: bytes) -> Dict:
    """
    使用 pdfplumber 解析 PDF 並返回發票資料

    注意：根據實際發票格式調整解析邏輯
    """
    invoice_data = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            if not pdf.pages:
                logger.warning("PDF 無內容頁")
                return invoice_data
                
            # 取得第一頁內容
            page = pdf.pages[0]
            text = page.extract_text()
            
            if not text:
                logger.warning("無法提取 PDF 文字內容")
                return invoice_data
                
            # 為除錯記錄前 1000 個字元
            logger.info(f"提取到的 PDF 文字內容(前 1000 字元): {text[:1000]}")

            # 統一全形與半形冒號，避免解析失敗
            text = text.replace(":", "：")
            lines = text.split("\n")
            for line in lines:
                line = line.strip()
                # 發票號碼
                if "發票號碼" in line:
                    parts = line.split("：")
                    if len(parts) > 1:
                        invoice_data["invoice_number"] = parts[-1].strip()
                # 發票日期
                elif "發票日期" in line:
                    parts = line.split("：")
                    if len(parts) > 1:
                        invoice_data["invoice_date"] = parts[-1].strip()
                # 買受人
                elif "買受人" in line:
                    parts = line.split("：")
                    if len(parts) > 1:
                        invoice_data["buyer_name"] = parts[-1].strip()
                # 統一編號
                elif "統一編號" in line:
                    parts = line.split("：")
                    if len(parts) > 1:
                        invoice_data["tax_id"] = parts[-1].strip()
                # 金額相關
                elif "金額" in line:
                    try:
                        parts = line.split("：")
                        if len(parts) > 1:
                            amount_str = parts[-1].replace(",", "").strip()
                            amount = float(amount_str)
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
    """
    根據 email_id 與提供者，選擇適合的 Adapter 下載並處理附件，
    返回發票資料列表。

    注意：Google（Gmail）與 Microsoft 附件資料格式不同，因此 PDF 附件的處理流程也會略有差異。
    """
    try:
        provider = provider.lower()
        logger.info(f"開始處理郵件附件，提供者: {provider}, email_id: {email_id}")

        # 根據 email_id 特徵判斷附件來源
        if "AQMK" in email_id:  # Microsoft 郵件 ID 特徵
            logger.info("檢測到 Microsoft 格式的郵件 ID")
            adapter = MicrosoftAdapter(access_token)
        elif any(x in provider for x in ["gmail", "google"]):
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
                if invoice_data:  # 僅添加成功解析的結果
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