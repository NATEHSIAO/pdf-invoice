from fastapi import APIRouter, HTTPException, Response, Depends, Request, Header
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
import logging
import os
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.models.user import User, TokenInfo

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

class OAuthCallback(BaseModel):
    code: str

# 確保導出所需的函數和類型
__all__ = ["verify_token", "get_current_user"]

async def verify_token(token: str = Depends(oauth2_scheme)) -> TokenInfo:
    """驗證令牌並返回令牌信息"""
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
                logger.info(f"Google token info: {token_info}")
                return TokenInfo(
                    sub=token_info["sub"],
                    email=token_info["email"],
                    name=token_info.get("name"),
                    picture=token_info.get("picture"),
                    exp=int(token_info["exp"]),
                    scope=token_info["scope"],
                    provider="google"
                )
            
            # 嘗試驗證 Microsoft Token
            ms_response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if ms_response.status_code == 200:
                user_info = ms_response.json()
                logger.info(f"Microsoft user info: {user_info}")
                return TokenInfo(
                    sub=user_info["id"],
                    email=user_info["userPrincipalName"],
                    name=user_info.get("displayName"),
                    picture=None,
                    exp=int((datetime.now() + timedelta(hours=1)).timestamp()),
                    scope="openid profile email",
                    provider="microsoft"
                )
            
            raise HTTPException(
                status_code=401,
                detail="無效的認證令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
                
    except Exception as e:
        logger.error(f"Token 驗證過程發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"認證過程發生錯誤: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

class User(BaseModel):
    id: str
    provider: str
    access_token: str

async def get_current_user(authorization: str = Header(...)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="無效的存取令牌")
    token = authorization.split(" ")[1]

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v3/tokeninfo",
            params={"access_token": token}
        )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="存取令牌驗證失敗")

    token_info = response.json()
    user_data = {
        "id": token_info.get("sub"),
        "provider": "google",  # 或依實際邏輯決定 provider
        "access_token": token  # 將由前端傳來的 token 直接保留到 User 模型
    }
    try:
        user = User(**user_data)
    except Exception as e:
        raise HTTPException(status_code=401, detail="無效的使用者資訊")
    return user

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

@router.get("/auth/session")
async def get_session(current_user: User = Depends(get_current_user)):
    """獲取當前會話資訊"""
    try:
        return JSONResponse(
            content={
                "status": "success",
                "data": {
                    "user": {
                        "id": current_user.id,
                        "email": current_user.email,
                        "name": current_user.name,
                        "picture": current_user.picture,
                        "provider": current_user.provider
                    }
                }
            }
        )
    except Exception as e:
        logger.error(f"獲取會話資訊時發生錯誤: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e)
            }
        ) 