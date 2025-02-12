from fastapi import APIRouter, HTTPException, Response, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import httpx
import logging
import os

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
async def oauth_callback(provider: str, data: OAuthCallback):
    try:
        logger.info(f"收到 OAuth 回調請求: provider={provider}, code={data.code[:10]}...")
        
        if provider.upper() == "GOOGLE":
            token_url = "https://oauth2.googleapis.com/token"
            client_id = os.getenv("GOOGLE_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
            redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback/google")
            
            logger.info(f"Google OAuth 配置: client_id={client_id[:10]}..., redirect_uri={redirect_uri}")
            
            if not client_id or not client_secret:
                logger.error("缺少 Google OAuth 配置")
                raise HTTPException(status_code=500, detail="缺少 OAuth 配置")
            
            logger.info("開始交換 Google access token")
            async with httpx.AsyncClient() as client:
                token_data = {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": data.code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "scope": "https://www.googleapis.com/auth/gmail.readonly email profile",
                }
                logger.info(f"發送 token 請求: {token_url}")
                logger.info(f"請求資料: {token_data}")
                
                token_response = await client.post(token_url, data=token_data)
                
                logger.info(f"Token 回應狀態: {token_response.status_code}")
                logger.info(f"Token 回應內容: {token_response.text}")
                
                if token_response.status_code != 200:
                    logger.error(f"Google token 請求失敗: {token_response.text}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"無法獲取 access token: {token_response.text}"
                    )
                
                token_data = token_response.json()
                logger.info("成功獲取 Google access token")
                
                # 驗證 token
                token_info_response = await client.get(
                    "https://www.googleapis.com/oauth2/v3/tokeninfo",
                    params={"access_token": token_data["access_token"]}
                )
                
                logger.info(f"Token 驗證回應狀態: {token_info_response.status_code}")
                logger.info(f"Token 驗證回應內容: {token_info_response.text}")
                
                if token_info_response.status_code != 200:
                    logger.error(f"Token 驗證失敗: {token_info_response.text}")
                    raise HTTPException(
                        status_code=400,
                        detail="Token 驗證失敗"
                    )
                    
                token_info = token_info_response.json()
                
                # 獲取用戶信息
                user_info_response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {token_data['access_token']}"},
                )
                
                logger.info(f"用戶信息回應狀態: {user_info_response.status_code}")
                
                if user_info_response.status_code != 200:
                    logger.error(f"獲取用戶信息失敗: {user_info_response.text}")
                    raise HTTPException(
                        status_code=400,
                        detail="無法獲取用戶信息"
                    )
                
                user_info = user_info_response.json()
                logger.info("成功獲取用戶信息")
                
                return {
                    "access_token": token_data["access_token"],
                    "token_type": "bearer",
                    "expires_in": token_data.get("expires_in", 3600),
                    "refresh_token": token_data.get("refresh_token"),
                    "provider": "GOOGLE",
                    "user": {
                        "id": user_info["id"],
                        "email": user_info["email"],
                        "name": user_info.get("name"),
                        "picture": user_info.get("picture"),
                    },
                }
                
        elif provider.upper() == "MICROSOFT":
            token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            client_id = os.getenv("MICROSOFT_CLIENT_ID")
            client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
            redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:3000/auth/callback/microsoft")
            
            if not client_id or not client_secret:
                logger.error("缺少 Microsoft OAuth 配置")
                raise HTTPException(status_code=500, detail="缺少 OAuth 配置")
            
            logger.info("開始交換 Microsoft access token")
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    token_url,
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "code": data.code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                        "scope": "openid profile email Mail.Read",
                    },
                )
                
                if token_response.status_code != 200:
                    logger.error(f"Microsoft token 請求失敗: {token_response.text}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"無法獲取 access token: {token_response.text}"
                    )
                
                token_data = token_response.json()
                logger.info("成功獲取 Microsoft access token")
                
                # 獲取用戶信息
                user_info_response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {token_data['access_token']}"},
                )
                
                if user_info_response.status_code != 200:
                    logger.error(f"獲取 Microsoft 用戶信息失敗: {user_info_response.text}")
                    raise HTTPException(
                        status_code=400,
                        detail="無法獲取用戶信息"
                    )
                
                user_info = user_info_response.json()
                logger.info("成功獲取 Microsoft 用戶信息")
                
                return {
                    "access_token": token_data["access_token"],
                    "token_type": "bearer",
                    "expires_in": token_data.get("expires_in", 3600),
                    "refresh_token": token_data.get("refresh_token"),
                    "user": {
                        "id": user_info["id"],
                        "email": user_info["userPrincipalName"],
                        "name": user_info.get("displayName"),
                        "picture": None,
                    },
                }
        
        else:
            raise HTTPException(status_code=400, detail="不支援的認證提供者")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth 回調處理失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"認證處理失敗: {str(e)}")

@router.get("/auth/check")
async def check_auth():
    return Response(status_code=200)

@router.post("/auth/logout")
async def logout():
    return Response(status_code=200) 