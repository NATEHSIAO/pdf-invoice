import logging
from abc import ABC, abstractmethod
import httpx
import base64
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class EmailAdapter(ABC):
    def __init__(self, access_token: str):
        self.access_token = access_token

    @abstractmethod
    async def get_pdf_attachments(self, email_id: str) -> list:
        """根據 email_id 取得附件資料，並只返回符合 PDF 格式的附件列表"""
        pass

class GmailAdapter(EmailAdapter):
    async def get_pdf_attachments(self, email_id: str) -> list:
        attachments = []
        raw_attachments = await self._fetch_gmail_attachments(email_id)
        for att in raw_attachments:
            mime_type = att.get('mimeType', '').lower()
            filename = att.get('filename', '').lower()
            if mime_type == 'application/pdf' or filename.endswith('.pdf'):
                attachments.append(att)
                logger.info(f"找到 PDF 附件: {att.get('filename')}")
            else:
                logger.warning(f"Google 附件(檔名: {att.get('filename', '未知')}, MIME: {mime_type}) 不是 PDF，已跳過")
        return attachments

    async def _fetch_gmail_attachments(self, email_id: str) -> List[Dict[str, Any]]:
        """透過 Gmail API 取得附件列表"""
        try:
            logger.info(f"開始獲取 Gmail 郵件: {email_id}")
            async with httpx.AsyncClient() as client:
                # 先獲取郵件詳情
                response = await client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{email_id}",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                
                if response.status_code != 200:
                    logger.error(f"Gmail API 錯誤: {response.text}")
                    return []

                message_data = response.json()
                attachments = []
                
                if "payload" not in message_data:
                    logger.warning("郵件無 payload 資料")
                    return []
                    
                if "parts" not in message_data["payload"]:
                    logger.warning("郵件無 parts 資料")
                    return []

                for part in message_data["payload"]["parts"]:
                    if part.get("filename") and part.get("body", {}).get("attachmentId"):
                        # 獲取附件內容
                        att_response = await client.get(
                            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{email_id}/attachments/{part['body']['attachmentId']}",
                            headers={"Authorization": f"Bearer {self.access_token}"}
                        )
                        
                        if att_response.status_code != 200:
                            logger.error(f"獲取附件內容失敗: {att_response.text}")
                            continue
                            
                        att_data = att_response.json()
                        attachments.append({
                            "filename": part["filename"],
                            "mimeType": part.get("mimeType", ""),
                            "size": part.get("body", {}).get("size", 0),
                            "data": att_data.get("data", ""),  # base64 編碼的附件內容
                            "attachmentId": part["body"]["attachmentId"],
                            "messageId": email_id
                        })
                        logger.info(f"成功獲取附件: {part['filename']}")

                return attachments
        except Exception as e:
            logger.error(f"獲取 Gmail 附件時發生錯誤: {str(e)}")
            return []

class MicrosoftAdapter(EmailAdapter):
    async def get_pdf_attachments(self, email_id: str) -> list:
        attachments = []
        raw_attachments = await self._fetch_ms_attachments(email_id)
        for att in raw_attachments:
            content_type = att.get('contentType', '').lower()
            name = att.get('name', '').lower()
            if content_type == 'application/pdf' or name.endswith('.pdf'):
                attachments.append(att)
                logger.info(f"找到 PDF 附件: {att.get('name')}")
            else:
                logger.warning(f"Microsoft 附件(檔名: {att.get('name', '未知')}, 類型: {content_type}) 格式異常，判定非 PDF")
        return attachments

    async def _fetch_ms_attachments(self, email_id: str) -> List[Dict[str, Any]]:
        """透過 Microsoft Graph API 取得附件列表，如果附件較大則需額外呼叫 API 取得附件內容"""
        try:
            import urllib.parse
            encoded_message_id = urllib.parse.quote(email_id)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://graph.microsoft.com/v1.0/me/messages/{encoded_message_id}/attachments",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json",
                        "ConsistencyLevel": "eventual"
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Microsoft Graph API 錯誤: {response.text}")
                    return []

                data = response.json()
                attachments = []
                
                for att in data.get("value", []):
                    attachment_id = att.get("id")
                    content = att.get("contentBytes")
                    # 如果 contentBytes 不存在，嘗試額外呼叫 API 取得大附件內容
                    if not content:
                        content_url = f"https://graph.microsoft.com/v1.0/me/messages/{encoded_message_id}/attachments/{attachment_id}/$value"
                        content_resp = await client.get(content_url, headers={"Authorization": f"Bearer {self.access_token}"})
                        if content_resp.status_code == 200:
                            # 將二進位內容轉換為 base64 字串，以符合標準化處理的邏輯
                            content = base64.b64encode(content_resp.content).decode('utf-8')
                        else:
                            logger.error(f"獲取大附件內容失敗: {content_resp.text}")
                            continue
                    attachments.append({
                        "name": att.get("name", ""),
                        "contentType": att.get("contentType", ""),
                        "size": att.get("size", 0),
                        "id": attachment_id,
                        "messageId": email_id,
                        "content": content  # Microsoft 直接提供或經額外 API 取得的 base64 編碼附件內容
                    })
                    logger.info(f"成功獲取附件: {att.get('name', '未知')}")

                return attachments
        except Exception as e:
            logger.error(f"獲取 Microsoft 附件時發生錯誤: {str(e)}")
            return [] 