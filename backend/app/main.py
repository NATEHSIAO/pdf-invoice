from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routes import auth, email, pdf
import logging
import os

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    debug=True,
    lifespan=pdf.lifespan  # 加入 lifespan 管理
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含路由，統一加上 API 前綴
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(email.router, prefix="/api/emails", tags=["email"])
app.include_router(pdf.router, prefix="/api/pdf", tags=["pdf"])

@app.get("/")
async def root():
    return {"message": "PDF Invoice Manager API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# 改進錯誤處理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"全局錯誤處理: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": str(exc),
            "detail": getattr(exc, "detail", None)
        }
    ) 