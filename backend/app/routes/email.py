from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, validator
from datetime import datetime
from typing import List, Dict, Any
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
        logger.info(f"收到搜尋請求，完整請求內容: {request}")
        logger.info(f"Authorization 標頭: {authorization[:20]}..." if authorization else "無 Authorization 標頭")
        
        if not authorization or not authorization.startswith("Bearer "):
            logger.error("未提供有效的認證令牌")
            raise HTTPException(
                status_code=401,
                detail="未提供有效的認證令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = authorization.split(" ")[1]
        logger.info(f"使用 token: {token[:20]}...")
        
        # 驗證 token
        try:
            logger.info("開始驗證 token...")
            async with httpx.AsyncClient() as client:
                logger.info("發送 token 驗證請求到 Google API")
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v3/tokeninfo",
                    params={"access_token": token}
                )
                
                logger.info(f"Token 驗證響應狀態: {response.status_code}")
                logger.info(f"Token 驗證響應內容: {response.text}")
                
                if response.status_code != 200:
                    logger.error(f"Token 驗證失敗: {response.text}")
                    raise HTTPException(
                        status_code=401,
                        detail="無效的認證令牌",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                
                token_info = response.json()
                logger.info(f"Token 信息: {token_info}")
                
                required_scope = "https://www.googleapis.com/auth/gmail.readonly"
                if required_scope not in token_info.get("scope", ""):
                    logger.error(f"缺少必要的 scope: {required_scope}")
                    logger.error(f"當前 scope: {token_info.get('scope', '')}")
                    raise HTTPException(
                        status_code=403,
                        detail="缺少必要的郵件讀取權限"
                    )
        except httpx.RequestError as e:
            logger.error(f"Token 驗證請求失敗: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"認證服務暫時無法使用: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Token 驗證過程發生未預期的錯誤: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Token 驗證失敗: {str(e)}"
            )
        
        # 建立搜尋查詢
        try:
            query = await build_search_query(request)
            logger.info(f"搜尋查詢: {query}")
            
            # 初始化郵件服務並執行搜尋
            logger.info("初始化郵件服務...")
            email_service = EmailService(token, request.provider)
            
            logger.info("執行郵件搜尋...")
            raw_emails = await email_service.search_emails(query)
            logger.info(f"搜尋完成，原始郵件數量: {len(raw_emails)}")
            
            # 格式化並返回結果
            logger.info("開始格式化郵件...")
            emails = format_email_response(raw_emails)
            logger.info(f"格式化完成，最終郵件數量: {len(emails)}")
            
            return emails
            
        except Exception as service_error:
            logger.error(f"郵件服務錯誤: {str(service_error)}")
            logger.exception("完整錯誤堆疊:")
            if "Invalid Credentials" in str(service_error):
                raise HTTPException(
                    status_code=401,
                    detail="認證失敗，請重新登入"
                )
            raise HTTPException(
                status_code=500,
                detail=f"郵件搜尋失敗: {str(service_error)}"
            )
        
    except HTTPException as he:
        logger.error(f"HTTP 錯誤: {str(he)}")
        raise he
    except Exception as e:
        error_msg = str(e)
        logger.error(f"未預期的錯誤: {error_msg}")
        logger.exception("完整錯誤堆疊:")
        
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