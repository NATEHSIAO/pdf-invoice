from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, validator
from datetime import datetime
from typing import List, Dict, Any
import logging
import httpx

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/emails",
    tags=["email"]
)

# 基本模型定義
class DateRange(BaseModel):
    start: str
    end: str

    @validator('start', 'end')
    def validate_date_format(cls, v):
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
async def build_search_query(request: EmailSearchRequest) -> str:
    """建立搜尋查詢字串"""
    start_date = request.dateRange.start.replace("-", "/")
    end_date = request.dateRange.end.replace("-", "/")
    
    query_parts = []
    
    if request.provider == "GOOGLE":
        # Gmail 查詢格式
        query_parts.extend([
            f'subject:"{request.keywords}"',
            f'after:{start_date}',
            f'before:{end_date}'
        ])
        if request.folder != "INBOX":
            query_parts.append(f'in:{request.folder}')
    else:
        # Microsoft Graph API 查詢格式
        query_parts.extend([
            f'subject:"{request.keywords}"',
            f'received>={start_date}',
            f'received<={end_date}'
        ])
        if request.folder != "INBOX":
            query_parts.append(f'folder:{request.folder}')
    
    query = " ".join(query_parts)
    logger.info(f"構建查詢字串: {query} (提供者: {request.provider})")
    return query

def format_email_response(raw_emails: List[Dict[str, Any]]) -> List[EmailResponse]:
    """格式化郵件回應"""
    formatted_emails = []
    
    for email in raw_emails:
        try:
            # 解析寄件者資訊
            sender_info = email.get("from", "").split(" <", 1)
            sender_name = sender_info[0].strip()
            sender_email = sender_info[1].rstrip(">") if len(sender_info) > 1 else sender_name
            
            # 建立回應物件
            formatted_email = EmailResponse(
                id=email["id"],
                subject=email.get("subject", ""),
                sender=EmailSender(
                    name=sender_name,
                    email=sender_email
                ),
                date=email["date"],
                content=email.get("content", ""),
                has_attachments=bool(email.get("attachments")),
                attachments=[
                    Attachment(
                        filename=att["filename"],
                        mime_type=att["mimeType"],
                        size=att["size"]
                    ) for att in email.get("attachments", [])
                ]
            )
            formatted_emails.append(formatted_email)
            
        except Exception as e:
            logger.error(f"格式化郵件失敗: {str(e)}, email_id: {email.get('id', 'unknown')}")
            continue
    
    return formatted_emails

async def verify_token(token: str, provider: str) -> bool:
    """驗證 token 的有效性"""
    try:
        if provider == "GOOGLE":
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v3/tokeninfo",
                    params={"access_token": token}
                )
                
                if response.status_code != 200:
                    logger.error(f"Token 驗證失敗: {response.text}")
                    return False
                
                token_info = response.json()
                required_scope = "https://www.googleapis.com/auth/gmail.readonly"
                if required_scope not in token_info.get("scope", ""):
                    logger.error(f"缺少必要的 scope: {required_scope}")
                    return False
                    
                return True
        else:
            # Microsoft token 驗證邏輯
            return True
            
    except Exception as e:
        logger.error(f"Token 驗證過程發生錯誤: {str(e)}")
        return False

# API 端點
@router.post("/search", response_model=List[EmailResponse])
async def search_emails(
    request: EmailSearchRequest,
    authorization: str = Header(..., description="Bearer token")
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
        logger.info(f"收到搜尋請求: {request}")
        
        # 驗證 authorization header
        if not authorization or not authorization.startswith("Bearer "):
            logger.error("認證格式錯誤")
            raise HTTPException(
                status_code=401,
                detail="無效的認證格式，請使用 Bearer token"
            )
        
        token = authorization.split(" ")[1]
        if not token:
            logger.error("Token 為空")
            raise HTTPException(
                status_code=401,
                detail="認證 token 不能為空"
            )
            
        logger.info(f"使用 token: {token[:10]}...")
        
        # 驗證 token
        is_valid = await verify_token(token, request.provider)
        if not is_valid:
            logger.error("Token 驗證失敗")
            raise HTTPException(
                status_code=401,
                detail="認證失敗，請重新登入"
            )
        
        # 建立搜尋查詢
        query = await build_search_query(request)
        logger.info(f"搜尋查詢: {query}")
        
        try:
            # 初始化郵件服務並執行搜尋
            from app.services.email import EmailService
            email_service = EmailService(token, request.provider)
            raw_emails = await email_service.search_emails(query)
            
            # 格式化並返回結果
            emails = format_email_response(raw_emails)
            logger.info(f"成功搜尋到 {len(emails)} 封郵件")
            return emails
            
        except Exception as service_error:
            logger.error(f"郵件服務錯誤: {str(service_error)}")
            if "Invalid Credentials" in str(service_error):
                raise HTTPException(
                    status_code=401,
                    detail="認證失敗，請重新登入"
                )
            raise
        
    except HTTPException as he:
        logger.error(f"HTTP 錯誤: {str(he)}")
        raise he
    except Exception as e:
        error_msg = str(e)
        logger.error(f"未預期的錯誤: {error_msg}")
        
        if "Invalid Credentials" in error_msg or "invalid_grant" in error_msg or "expired" in error_msg:
            raise HTTPException(status_code=401, detail="認證已過期或無效，請重新登入")
        elif "unauthorized" in error_msg.lower():
            raise HTTPException(status_code=401, detail="未授權的存取，請重新登入")
        elif "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
            raise HTTPException(status_code=429, detail="請求過於頻繁，請稍後再試")
        elif "permission" in error_msg.lower() or "scope" in error_msg.lower():
            raise HTTPException(status_code=403, detail="權限不足，請確認郵件存取權限")
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"系統發生未預期的錯誤: {error_msg}"
            )