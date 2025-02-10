# PDF Invoice Parser

一個自動化的 PDF 發票解析工具，可以從 Gmail 或 Outlook 郵箱中批量下載發票並解析成 CSV 格式。

## 功能特點

- 支持 Google 和 Microsoft 帳號登入
- 自動搜尋郵箱中的發票附件
- 批量下載 PDF 發票
- 智能解析發票內容
- 匯出成 CSV 格式

## 技術棧

- 前端：React + TypeScript + Tailwind CSS
- 後端：Python (FastAPI)
- 認證：OAuth2.0 (Google + Microsoft)
- 部署：Vercel

## 本地開發

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 後端

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

## 環境變數

在專案根目錄創建 `.env` 文件，並設置以下環境變數：

```
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:5174/auth/callback

MICROSOFT_CLIENT_ID=your_microsoft_client_id
MICROSOFT_CLIENT_SECRET=your_microsoft_client_secret
MICROSOFT_REDIRECT_URI=http://localhost:5174/auth/microsoft/callback

VITE_API_URL=http://localhost:8000
```

## 部署

本專案使用 Vercel 進行部署。在 Vercel 上設置環境變數後，推送到 main 分支即可自動部署。

## 授權

MIT License
