from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import logging
from datetime import datetime
import zipfile
import tempfile
import os
from pathlib import Path

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["pdf"])

class InvoiceData(BaseModel):
    email_subject: str
    email_sender: str
    email_date: str
    invoice_number: str
    invoice_date: str
    buyer_name: str
    buyer_tax_id: str
    seller_name: str
    taxable_amount: float
    tax_free_amount: float
    zero_tax_amount: float
    tax_amount: float
    total_amount: float

class AnalysisProgress(BaseModel):
    total: int
    current: int
    status: str
    message: str

class AnalysisResult(BaseModel):
    invoices: List[InvoiceData]
    failed_files: List[str]
    download_url: Optional[str] = None

@router.post("/pdf/analyze")
async def analyze_pdfs(email_ids: List[str]) -> AnalysisResult:
    try:
        logger.info(f"開始解析 PDF，郵件 IDs: {email_ids}")
        
        # 測試數據
        test_invoices = [
            InvoiceData(
                email_subject="電子發票通知 - 訂單 #A001",
                email_sender="全聯實業 (invoice@pxmart.com.tw)",
                email_date="2024-02-09T10:30:00Z",
                invoice_number="KF19133656",
                invoice_date="2024-02-09",
                buyer_name="測試公司",
                buyer_tax_id="12345678",
                seller_name="全聯實業股份有限公司",
                taxable_amount=1000.0,
                tax_free_amount=0.0,
                zero_tax_amount=0.0,
                tax_amount=50.0,
                total_amount=1050.0
            ),
            InvoiceData(
                email_subject="您的電子發票 - 訂單 #B002",
                email_sender="家樂福量販店 (invoice@carrefour.com.tw)",
                email_date="2024-02-08T14:15:00Z",
                invoice_number="KG22445678",
                invoice_date="2024-02-08",
                buyer_name="測試公司",
                buyer_tax_id="12345678",
                seller_name="家樂福股份有限公司",
                taxable_amount=2000.0,
                tax_free_amount=0.0,
                zero_tax_amount=0.0,
                tax_amount=100.0,
                total_amount=2100.0
            ),
            InvoiceData(
                email_subject="電子發票開立通知 #C003",
                email_sender="大潤發超市 (invoice@rt-mart.com.tw)",
                email_date="2024-02-07T09:45:00Z",
                invoice_number="KH33556789",
                invoice_date="2024-02-07",
                buyer_name="測試公司",
                buyer_tax_id="12345678",
                seller_name="大潤發流通事業股份有限公司",
                taxable_amount=3000.0,
                tax_free_amount=0.0,
                zero_tax_amount=0.0,
                tax_amount=150.0,
                total_amount=3150.0
            ),
            InvoiceData(
                email_subject="發票通知 - 訂單 #D004",
                email_sender="好市多購物中心 (invoice@costco.com.tw)",
                email_date="2024-02-06T16:20:00Z",
                invoice_number="KJ44667890",
                invoice_date="2024-02-06",
                buyer_name="測試公司",
                buyer_tax_id="12345678",
                seller_name="好市多股份有限公司",
                taxable_amount=4000.0,
                tax_free_amount=0.0,
                zero_tax_amount=0.0,
                tax_amount=200.0,
                total_amount=4200.0
            ),
            InvoiceData(
                email_subject="電子發票 - 訂單 #E005",
                email_sender="愛買量販店 (invoice@fe-amart.com.tw)",
                email_date="2024-02-05T11:50:00Z",
                invoice_number="KL55778901",
                invoice_date="2024-02-05",
                buyer_name="測試公司",
                buyer_tax_id="12345678",
                seller_name="愛買量販店股份有限公司",
                taxable_amount=5000.0,
                tax_free_amount=0.0,
                zero_tax_amount=0.0,
                tax_amount=250.0,
                total_amount=5250.0
            )
        ]
        
        # 生成一個唯一的批次 ID
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return AnalysisResult(
            invoices=test_invoices,
            failed_files=[],
            download_url=f"/api/pdf/download/{batch_id}"
        )
        
    except Exception as e:
        logger.error(f"PDF 解析失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pdf/progress")
async def get_analysis_progress() -> AnalysisProgress:
    # 測試進度回應
    return AnalysisProgress(
        total=5,
        current=3,
        status="processing",
        message="正在解析 PDF 文件..."
    )

@router.get("/pdf/download/{batch_id}")
async def download_pdfs(batch_id: str):
    try:
        logger.info(f"開始下載 PDF，批次 ID: {batch_id}")
        
        # 建立臨時目錄
        temp_dir = tempfile.mkdtemp()
        try:
            # 建立 ZIP 文件
            zip_filename = f"invoices_{batch_id}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)
            logger.info(f"建立 ZIP 文件: {zip_path}")
            
            # 測試 PDF 文件路徑
            test_pdf_path = "../../docs/發票明細(示意圖)_KF19133656_20250121132319128.pdf"
            if not os.path.exists(test_pdf_path):
                logger.error(f"找不到測試 PDF 文件: {test_pdf_path}")
                raise HTTPException(status_code=404, detail="找不到 PDF 文件")
            
            # 建立 ZIP 文件
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                logger.info("開始添加文件到 ZIP")
                # 添加多個 PDF 文件，使用不同的名稱
                for i in range(1, 6):
                    invoice_number = f"KF{19133655 + i}"
                    archive_name = f"發票明細_訂單{i}_{invoice_number}.pdf"
                    logger.info(f"添加文件: {archive_name}")
                    zip_file.write(test_pdf_path, archive_name)
            
            # 檢查 ZIP 文件是否成功建立
            if not os.path.exists(zip_path):
                logger.error("ZIP 文件建立失敗")
                raise HTTPException(status_code=500, detail="無法建立 ZIP 文件")
            
            logger.info("準備返回 ZIP 文件")
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename=zip_filename,
                background=None  # 禁用背景任務
            )
            
        except Exception as e:
            logger.error(f"處理 ZIP 文件時發生錯誤: {str(e)}")
            raise
        finally:
            # 清理臨時目錄
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.error(f"清理臨時目錄失敗: {str(e)}")
            
    except Exception as e:
        logger.error(f"PDF 下載失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 