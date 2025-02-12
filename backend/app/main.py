from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, email, pdf
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(debug=True)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含路由
app.include_router(auth.router)
app.include_router(email.router, prefix="/api")
app.include_router(pdf.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "PDF Invoice Manager API"}

# 錯誤處理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"全局錯誤處理: {str(exc)}")
    return {"detail": str(exc)} 