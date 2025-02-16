from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

def create_sample_invoice():
    # 確保目錄存在
    os.makedirs("tests/fixtures", exist_ok=True)
    
    # 使用 Helvetica 字體，但將中文字轉換為 Unicode 編碼
    c = canvas.Canvas("tests/fixtures/sample_invoice.pdf", pagesize=letter)
    c.setFont("Helvetica", 12)
    
    # 添加發票內容（使用 Unicode 編碼）
    content = [
        ("Invoice Number", "INV-2024001"),
        ("Invoice Date", "2024-03-01"),
        ("Buyer Name", "Test Company"),
        ("Buyer Tax ID", "12345678"),
        ("Seller Name", "Supplier"),
        ("Taxable Amount", "10000"),
        ("Tax Free Amount", "0"),
        ("Zero Tax Amount", "0"),
        ("Tax Amount", "500"),
        ("Total Amount", "10500")
    ]
    
    y = 750
    for label, value in content:
        text = f"{label}: {value}"
        c.drawString(100, y, text)
        y -= 20
    
    c.save()
    print("Sample invoice PDF created successfully")

if __name__ == "__main__":
    create_sample_invoice() 