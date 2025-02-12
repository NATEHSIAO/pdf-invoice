from fastapi import APIRouter, HTTPException, Response, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import httpx
import logging
import os
import requests

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class OAuthCallback(BaseModel):
    code: str

async def get_current_user(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(
            status_code=401,
            detail="未提供認證令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        async with httpx.AsyncClient() as client:
            # 嘗試驗證 Google Token
            google_response = await client.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"access_token": token}
            )
            
            if google_response.status_code == 200:
                token_info = google_response.json()
                required_scope = "https://www.googleapis.com/auth/gmail.readonly"
                if required_scope not in token_info.get("scope", ""):
                    logger.error(f"缺少必要的 scope: {required_scope}")
                    raise HTTPException(
                        status_code=403,
                        detail="缺少必要的郵件讀取權限"
                    )
                return token
            
            # 如果不是 Google Token，嘗試驗證 Microsoft Token
            ms_response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if ms_response.status_code == 200:
                return token
            
            # 如果兩種驗證都失敗
            logger.error("Token 驗證失敗：既不是有效的 Google Token 也不是有效的 Microsoft Token")
            raise HTTPException(
                status_code=401,
                detail="無效的認證令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token 驗證過程發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="認證過程發生錯誤",
            headers={"WWW-Authenticate": "Bearer"},
        )
            
    return token

@router.post("/auth/callback/{provider}")
async def oauth_callback(provider: str, request: Request):
    try:
        data = await request.json()
        code = data.get("code")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")
        
        # 根據提供者獲取配置
        if provider.upper() == "GOOGLE":
            client_id = os.getenv("NEXT_PUBLIC_GOOGLE_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
            token_url = "https://oauth2.googleapis.com/token"
        elif provider.upper() == "MICROSOFT":
            client_id = os.getenv("NEXT_PUBLIC_MICROSOFT_CLIENT_ID")
            client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
            token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        else:
            raise HTTPException(status_code=400, detail="不支援的認證提供者")
        
        # 從請求標頭獲取來源
        origin = request.headers.get("origin", "http://localhost:3000")
        redirect_uri = f"{origin}/auth/callback/{provider.lower()}"
        
        logger.info(f"OAuth callback received for provider: {provider}")
        logger.debug(f"Using client_id: {client_id}")
        logger.debug(f"Redirect URI: {redirect_uri}")
        
        if not all([client_id, client_secret]):
            logger.error("Missing OAuth configuration")
            raise HTTPException(status_code=500, detail="OAuth configuration is incomplete")
        
        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=token_data)
            
            if response.status_code != 200:
                logger.error(f"Token request failed: {response.text}")
                raise HTTPException(status_code=400, detail=f"無法獲取 access token: {response.text}")
            
            token_response = response.json()
            
            # 獲取用戶信息
            if provider.upper() == "GOOGLE":
                user_info = await get_google_user_info(token_response["access_token"])
            else:
                user_info = await get_microsoft_user_info(token_response["access_token"])
            
            return {
                "access_token": token_response["access_token"],
                "token_type": "bearer",
                "expires_in": token_response.get("expires_in", 3600),
                "refresh_token": token_response.get("refresh_token"),
                "user": user_info
            }
            
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

async def get_google_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="無法獲取用戶信息")
        user_info = response.json()
        return {
            "id": user_info["id"],
            "email": user_info["email"],
            "name": user_info.get("name"),
            "picture": user_info.get("picture")
        }

async def get_microsoft_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="無法獲取用戶信息")
        user_info = response.json()
        return {
            "id": user_info["id"],
            "email": user_info["userPrincipalName"],
            "name": user_info.get("displayName"),
            "picture": None
        }

@router.get("/auth/check")
async def check_auth():
    return Response(status_code=200)

@router.post("/auth/logout")
async def logout():
    return Response(status_code=200) 