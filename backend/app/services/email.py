from typing import List, Optional, Dict, Any, Union
import httpx
import base64
import logging
from datetime import datetime
from email import message_from_bytes
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, access_token: str, provider: str = "GOOGLE"):
        self.access_token = access_token
        self.provider = provider.upper()
        if self.provider == "GOOGLE":
            self.base_url = "https://gmail.googleapis.com/gmail/v1/users/me"
        elif self.provider == "MICROSOFT":
            self.base_url = "https://graph.microsoft.com/v1.0/me"
        else:
            raise ValueError(f"不支援的郵件提供者: {provider}")
        
    async def search_emails(self, query: Union[str, Dict[str, str]]) -> List[Dict[str, Any]]:
        """搜尋郵件"""
        try:
            logger.info(f"搜尋查詢: {query} (提供者: {self.provider})")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                if self.provider == "GOOGLE":
                    if isinstance(query, dict):
                        raise ValueError("Google 搜尋需要字串格式的查詢")
                    return await self._search_gmail(client, query)
                else:
                    if isinstance(query, str):
                        raise ValueError("Microsoft 搜尋需要字典格式的查詢")
                    return await self._search_microsoft(client, query)
                    
        except Exception as e:
            logger.error(f"搜尋郵件時發生錯誤: {str(e)}")
            raise

    async def _search_gmail(self, client: httpx.AsyncClient, query: str) -> List[Dict[str, Any]]:
        """Gmail 搜尋實作"""
        try:
            logger.info(f"執行 Gmail 搜尋: {query}")
            
            # 記錄請求詳情
            logger.info(f"Gmail API 請求 URL: {self.base_url}/messages")
            logger.info(f"Gmail API 請求參數: q={query}, maxResults=50")
            
            response = await client.get(
                f"{self.base_url}/messages",
                params={
                    "q": query,
                    "maxResults": 50
                },
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            # 記錄響應詳情
            logger.info(f"Gmail API 響應狀態碼: {response.status_code}")
            logger.info(f"Gmail API 響應內容: {response.text[:500]}")  # 只記錄前500個字符
            
            if response.status_code == 401:
                logger.error("認證失敗或 token 已過期")
                raise Exception("Invalid Credentials")
            elif response.status_code == 403:
                logger.error("權限不足")
                raise Exception("Permission Denied")
            elif response.status_code != 200:
                error_text = response.text
                logger.error(f"Gmail 搜尋失敗: {error_text}")
                raise Exception(f"Gmail API 錯誤: {error_text}")
            
            data = response.json()
            messages = data.get("messages", [])
            logger.info(f"Gmail 找到 {len(messages)} 封郵件")
            
            if not messages:
                return []
            
            # 使用 asyncio.gather 並行處理
            import asyncio
            emails = await asyncio.gather(*[
                self._get_gmail_message(client, message["id"])
                for message in messages
            ])
            
            # 過濾掉 None 值並記錄日誌
            valid_emails = [email for email in emails if email]
            logger.info(f"成功處理 {len(valid_emails)}/{len(messages)} 封郵件")
            
            return valid_emails
        except Exception as e:
            logger.error(f"Gmail 搜尋過程發生錯誤: {str(e)}")
            raise

    async def _get_gmail_message(self, client: httpx.AsyncClient, message_id: str) -> Optional[Dict[str, Any]]:
        """獲取 Gmail 郵件詳細信息"""
        try:
            response = await client.get(
                f"{self.base_url}/messages/{message_id}",
                params={"format": "full"},
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            if response.status_code != 200:
                logger.error(f"獲取 Gmail 郵件詳細信息失敗: {response.text}")
                return None
            
            message_data = response.json()
            logger.info(f"獲取到郵件資料: {message_data.keys()}")
            
            # 解析郵件標頭
            headers = {
                header["name"].lower(): header["value"]
                for header in message_data["payload"]["headers"]
            }
            
            # 解析寄件者資訊
            from_header = headers.get("from", "")
            logger.info(f"原始寄件者資訊: {from_header}")
            
            # 嘗試解析 "name <email>" 格式
            sender_name = from_header
            sender_email = from_header
            
            if "<" in from_header and ">" in from_header:
                try:
                    name_part = from_header.split("<")[0].strip()
                    email_part = from_header.split("<")[1].split(">")[0].strip()
                    
                    if name_part:
                        sender_name = name_part
                    sender_email = email_part
                except Exception as e:
                    logger.error(f"解析寄件者資訊失敗: {str(e)}")
            
            logger.info(f"解析後的寄件者資訊: name={sender_name}, email={sender_email}")
            
            # 遞迴搜索附件
            attachments = []
            def extract_attachments(payload):
                if "parts" in payload:
                    for part in payload["parts"]:
                        if part.get("filename"):
                            attachment = {
                                "filename": part["filename"],
                                "mimeType": part["mimeType"],
                                "size": part.get("body", {}).get("size", 0),
                                "attachmentId": part.get("body", {}).get("attachmentId")
                            }
                            logger.info(f"找到附件: {attachment}")
                            attachments.append(attachment)
                        if "parts" in part:
                            extract_attachments(part)
                elif payload.get("filename"):
                    attachment = {
                        "filename": payload["filename"],
                        "mimeType": payload["mimeType"],
                        "size": payload.get("body", {}).get("size", 0),
                        "attachmentId": payload.get("body", {}).get("attachmentId")
                    }
                    logger.info(f"找到附件: {attachment}")
                    attachments.append(attachment)

            extract_attachments(message_data["payload"])
            logger.info(f"總共找到 {len(attachments)} 個附件")
            
            # 解析郵件內容
            content = self._get_email_content(message_data["payload"])
            
            # 解析日期
            date_str = headers.get("date", "")
            try:
                date = parsedate_to_datetime(date_str).isoformat()
            except:
                date = datetime.now().isoformat()
                logger.warning(f"無法解析郵件日期 '{date_str}'，使用當前時間")
            
            return {
                "id": message_id,
                "subject": headers.get("subject", "(無主旨)"),
                "from": f"{sender_name} <{sender_email}>",
                "date": date,
                "content": content,
                "hasAttachments": bool(attachments),
                "attachments": attachments
            }
        except Exception as e:
            logger.error(f"處理 Gmail 郵件 {message_id} 時發生錯誤: {str(e)}")
            return None

    def _get_email_content(self, payload: Dict[str, Any]) -> str:
        """遞迴解析郵件內容"""
        if payload.get("mimeType") == "text/plain":
            if "data" in payload.get("body", {}):
                try:
                    return base64.urlsafe_b64decode(
                        payload["body"]["data"].encode("ASCII")
                    ).decode("utf-8")
                except Exception as e:
                    logger.error(f"解析郵件內容失敗: {str(e)}")
                    return ""
        
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    if "data" in part.get("body", {}):
                        try:
                            return base64.urlsafe_b64decode(
                                part["body"]["data"].encode("ASCII")
                            ).decode("utf-8")
                        except Exception as e:
                            logger.error(f"解析郵件內容失敗: {str(e)}")
                            return ""
        
        return ""

    async def _search_microsoft(self, client: httpx.AsyncClient, query: Dict[str, str]) -> List[Dict[str, Any]]:
        """Microsoft Graph API 搜尋實作"""
        try:
            logger.info(f"執行 Microsoft Graph API 搜尋: {query}")
            
            # 先只獲取基本郵件資訊
            response = await client.get(
                f"{self.base_url}/messages",
                params={
                    **query,
                    "$select": "id,subject,from,receivedDateTime,body,hasAttachments"
                },
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                    "ConsistencyLevel": "eventual",
                    "Prefer": "outlook.body-content-type=\"text\""
                }
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Microsoft 搜尋失敗: {error_text}")
                raise Exception(f"Microsoft Graph API 錯誤: {error_text}")
            
            data = response.json()
            messages = data.get("value", [])
            logger.info(f"Microsoft 找到 {len(messages)} 封郵件")
            
            formatted_messages = []
            for msg in messages:
                try:
                    msg_id = msg.get("id")
                    logger.info(f"處理郵件 ID: {msg_id}")
                    
                    # 格式化郵件基本資訊
                    formatted_email = {
                        "id": msg_id,
                        "subject": msg.get("subject", "(無主旨)"),
                        "from": f"{msg['from']['emailAddress'].get('name', '')} <{msg['from']['emailAddress']['address']}>",
                        "date": msg["receivedDateTime"],
                        "content": msg.get("body", {}).get("content", ""),
                        "hasAttachments": msg.get("hasAttachments", False),
                        "attachments": []
                    }
                    
                    # 如果有附件，單獨獲取附件資訊
                    if formatted_email["hasAttachments"]:
                        try:
                            # 使用單獨的請求獲取附件資訊
                            att_response = await client.get(
                                f"{self.base_url}/messages/{msg_id}/attachments",
                                headers={
                                    "Authorization": f"Bearer {self.access_token}",
                                    "Accept": "application/json"
                                }
                            )
                            
                            if att_response.status_code == 200:
                                att_data = att_response.json()
                                attachments = []
                                for att in att_data.get("value", []):
                                    attachment = {
                                        "filename": att.get("name", ""),
                                        "mimeType": att.get("contentType", ""),
                                        "size": att.get("size", 0),
                                        "attachmentId": att.get("id")
                                    }
                                    attachments.append(attachment)
                                    logger.info(f"找到附件: {attachment}")
                                formatted_email["attachments"] = attachments
                            else:
                                logger.error(f"獲取附件資訊失敗: {att_response.text}")
                        except Exception as att_error:
                            logger.error(f"處理附件時發生錯誤: {str(att_error)}")
                    
                    formatted_messages.append(formatted_email)
                    logger.info(f"成功處理郵件 ID: {msg_id}")
                    
                except Exception as msg_error:
                    logger.error(f"處理郵件時發生錯誤: {str(msg_error)}, 郵件 ID: {msg.get('id')}")
                    logger.error(f"郵件資料: {msg}")
                    continue
            
            logger.info(f"成功格式化 {len(formatted_messages)}/{len(messages)} 封郵件")
            return formatted_messages
            
        except Exception as e:
            logger.error(f"Microsoft Graph API 搜尋過程發生錯誤: {str(e)}")
            raise

    async def _get_microsoft_attachments(self, client: httpx.AsyncClient, message_id: str) -> List[Dict[str, Any]]:
        """獲取 Microsoft 郵件附件信息"""
        response = await client.get(
            f"{self.base_url}/messages/{message_id}/attachments",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        
        if response.status_code != 200:
            logger.error(f"獲取 Microsoft 附件失敗: {response.text}")
            return []
            
        data = response.json()
        attachments = []
        for att in data.get("value", []):
            attachments.append({
                "filename": att.get("name", ""),
                "mimeType": att.get("contentType", ""),
                "size": att.get("size", 0),
                "attachmentId": att.get("id")
            })
            
        return attachments

    async def get_email_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """獲取郵件詳細信息"""
        try:
            logger.info(f"開始獲取郵件詳細信息: message_id={message_id}, provider={self.provider}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                if self.provider == "GOOGLE":
                    return await self._get_gmail_message(client, message_id)
                else:
                    # Microsoft Graph API
                    logger.info(f"獲取 Microsoft 郵件詳細信息: {message_id}")
                    
                    # URL 編碼郵件 ID
                    import urllib.parse
                    encoded_message_id = urllib.parse.quote(message_id)
                    
                    # 使用 v1.0 端點
                    response = await client.get(
                        f"https://graph.microsoft.com/v1.0/me/messages/{encoded_message_id}",
                        params={
                            "$select": "id,subject,from,receivedDateTime,body,hasAttachments"
                        },
                        headers={
                            "Authorization": f"Bearer {self.access_token}",
                            "Accept": "application/json",
                            "Prefer": "outlook.body-content-type=\"text\"",
                            "ConsistencyLevel": "eventual"
                        }
                    )
                    
                    if response.status_code == 404:
                        logger.error(f"郵件不存在: {message_id}")
                        return None
                    elif response.status_code == 401:
                        logger.error("認證失敗或 token 已過期")
                        raise Exception("Invalid Credentials")
                    elif response.status_code == 403:
                        logger.error("權限不足")
                        raise Exception("Permission Denied")
                    elif response.status_code != 200:
                        error_text = response.text
                        logger.error(f"獲取 Microsoft 郵件詳細信息失敗: {error_text}")
                        return None
                    
                    msg = response.json()
                    logger.info(f"獲取到 Microsoft 郵件資料: {msg.keys()}")
                    
                    # 獲取附件資訊
                    attachments = []
                    if msg.get("hasAttachments"):
                        try:
                            att_response = await client.get(
                                f"https://graph.microsoft.com/v1.0/me/messages/{encoded_message_id}/attachments",
                                headers={
                                    "Authorization": f"Bearer {self.access_token}",
                                    "Accept": "application/json",
                                    "ConsistencyLevel": "eventual"
                                }
                            )
                            
                            if att_response.status_code == 200:
                                att_data = att_response.json()
                                for att in att_data.get("value", []):
                                    attachment = {
                                        "filename": att.get("name", ""),
                                        "mimeType": att.get("contentType", ""),
                                        "size": att.get("size", 0),
                                        "attachmentId": att.get("id")
                                    }
                                    attachments.append(attachment)
                                    logger.info(f"找到附件: {attachment}")
                            else:
                                logger.error(f"獲取附件資訊失敗: {att_response.text}")
                        except Exception as att_error:
                            logger.error(f"處理附件時發生錯誤: {str(att_error)}")
                            logger.exception("附件錯誤堆疊:")
                    
                    return {
                        "id": msg["id"],
                        "subject": msg.get("subject", "(無主旨)"),
                        "from": f"{msg['from']['emailAddress'].get('name', '')} <{msg['from']['emailAddress']['address']}>",
                        "date": msg["receivedDateTime"],
                        "content": msg.get("body", {}).get("content", ""),
                        "hasAttachments": bool(attachments),
                        "attachments": attachments
                    }
                
        except Exception as e:
            logger.error(f"獲取郵件詳細信息時發生錯誤: {str(e)}")
            logger.exception("完整錯誤堆疊:")
            return None 