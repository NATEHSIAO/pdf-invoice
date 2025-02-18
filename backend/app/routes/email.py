from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, validator, field_validator
from datetime import datetime
from typing import List, Dict, Any, Union
import logging
import httpx
from app.routes.auth import oauth2_scheme
from app.services.email import EmailService

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["email"])

# 基本模型定義
class DateRange(BaseModel):
    start: str
    end: str

    @field_validator('start', 'end')
    def validate_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('日期格式必須為 YYYY-MM-DD')

class EmailSearchRequest(BaseModel):
    provider: str
    keywords: str
    dateRange: DateRange
    folder: str = "INBOX"  # 預設值為 INBOX

    @validator('provider')
    def validate_provider(cls, v):
        providers = ["GOOGLE", "MICROSOFT"]
        if v not in providers:
            raise ValueError(f'提供者必須是以下其中之一: {", ".join(providers)}')
        return v

    @validator('folder')
    def validate_folder(cls, v):
        folders = ["INBOX", "ARCHIVE", "SENT", "DRAFT", "TRASH"]
        if v not in folders:
            raise ValueError(f'信件夾必須是以下其中之一: {", ".join(folders)}')
        return v

class EmailSender(BaseModel):
    name: str
    email: str

class Attachment(BaseModel):
    filename: str
    mime_type: str
    size: int

class EmailResponse(BaseModel):
    id: str
    subject: str
    sender: EmailSender
    date: str
    content: str
    has_attachments: bool
    attachments: List[Attachment] = []

# 輔助函數
async def build_search_query(request: EmailSearchRequest) -> Union[str, Dict[str, str]]:
    """建立搜尋查詢字串"""
    try:
        start_date = request.dateRange.start.replace("-", "/")
        end_date = request.dateRange.end.replace("-", "/")
        
        if request.provider == "GOOGLE":
            # Gmail 查詢格式
            query_parts = [
                f'subject:"{request.keywords}"',
                f'after:{start_date}',
                f'before:{end_date}'
            ]
            if request.folder != "INBOX":
                query_parts.append(f'in:{request.folder}')
            query = " ".join(query_parts)
        else:
            # Microsoft Graph API 查詢格式
            filter_conditions = [
                f"receivedDateTime ge {request.dateRange.start}T00:00:00Z",
                f"receivedDateTime le {request.dateRange.end}T23:59:59Z",
                f"contains(subject, '{request.keywords}')"
            ]
            
            query = {
                "$filter": " and ".join(filter_conditions),
                "$select": "id,subject,from,receivedDateTime,body,hasAttachments",
                "$orderby": "receivedDateTime desc",
                "$top": 50
            }
            
            if request.folder != "INBOX":
                query["folderPath"] = request.folder
        
        logger.info(f"構建查詢字串: {query} (提供者: {request.provider})")
        return query
        
    except Exception as e:
        logger.error(f"構建查詢字串時發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"構建查詢字串失敗: {str(e)}"
        )

def format_email_response(raw_emails: List[Dict[str, Any]]) -> List[EmailResponse]:
    """格式化郵件回應"""
    formatted_emails = []
    
    for email in raw_emails:
        try:
            logger.info(f"開始格式化郵件: {email.get('id', 'unknown')}")
            
            # 解析寄件者資訊
            from_value = email.get("from", "")
            logger.info(f"原始寄件者資訊: {from_value}")
            
            # 嘗試解析 "name <email>" 格式
            if "<" in from_value and ">" in from_value:
                sender_name = from_value.split("<")[0].strip()
                sender_email = from_value.split("<")[1].split(">")[0].strip()
            else:
                # 如果沒有標準格式，使用整個值作為名稱和郵件
                sender_name = from_value
                sender_email = from_value
            
            logger.info(f"解析後的寄件者資訊: name={sender_name}, email={sender_email}")
            
            # 建立回應物件
            formatted_email = EmailResponse(
                id=email["id"],
                subject=email.get("subject", "（無主旨）"),
                sender=EmailSender(
                    name=sender_name,
                    email=sender_email
                ),
                date=email.get("date", datetime.now().isoformat()),
                content=email.get("content", ""),
                has_attachments=bool(email.get("attachments")),
                attachments=[
                    Attachment(
                        filename=att.get("filename", "unknown"),
                        mime_type=att.get("mimeType", "application/octet-stream"),
                        size=att.get("size", 0)
                    ) for att in email.get("attachments", [])
                ]
            )
            
            logger.info(f"郵件格式化成功: {formatted_email.dict()}")
            formatted_emails.append(formatted_email)
            
        except Exception as e:
            logger.error(f"格式化郵件失敗: {str(e)}, email_id: {email.get('id', 'unknown')}")
            logger.exception("完整錯誤堆疊:")
            continue
    
    return formatted_emails

async def verify_token(token: str, provider: str) -> bool:
    """驗證 token 的有效性"""
    try:
        async with httpx.AsyncClient() as client:
            if provider == "GOOGLE":
                # Google OAuth2 token 驗證
                response = await client.get(
                    "https://oauth2.googleapis.com/tokeninfo",  # 改用新的端點
                    params={"access_token": token}
                )
            else:
                # Microsoft token 驗證
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {token}"}
                )
            
            if response.status_code == 200:
                return True
            
            logger.error(f"Token 驗證失敗: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Token 驗證過程發生錯誤: {str(e)}")
        return False

# API 端點
@router.post("/search", response_model=List[EmailResponse])
async def search_emails(
    request: EmailSearchRequest,
    authorization: str = Header(None)
) -> List[EmailResponse]:
    """
    搜尋郵件 API
    
    參數:
    - request: 搜尋請求參數
    - authorization: Bearer token
    
    返回:
    - List[EmailResponse]: 郵件列表
    """
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="未提供有效的認證令牌"
            )
        
        token = authorization.split(" ")[1]
        
        # 驗證 token
        is_valid = await verify_token(token, request.provider)
        if not is_valid:
            raise HTTPException(
                status_code=401,
                detail="認證令牌無效或已過期"
            )
        
        # 建立搜尋查詢
        query = await build_search_query(request)
        email_service = EmailService(token, request.provider)
        raw_emails = await email_service.search_emails(query)
        
        return format_email_response(raw_emails)
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"搜尋郵件時發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )