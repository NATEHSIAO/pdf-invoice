# FileStructure.md

## 專案概述

本專案為前後端整合系統，前端使用 Next.js 與 TypeScript，後端使用 FastAPI 與 Python。Docker 用於容器化各個服務。

## 專案目錄結構

```
.
├── README.md                # 專案概覽、安裝與使用說明
├── .gitignore              # Git 忽略檔案設定
├── .env                    # 環境變數設定檔（OAuth、API Keys）
│
├── docs/                   # 文件資料夾
│   ├── prd.md             # 產品需求文件
│   ├── API doc.md         # API 文件
│   ├── FileStructure.md   # 專案目錄結構文件
│   └── cursorrules.md     # 開發規範
│
├── frontend/              # 前端專案目錄 (Next.js/TypeScript)
│   ├── public/           # 靜態資源
│   ├── src/
│   │   ├── app/         # Next.js App Router 目錄
│   │   │   ├── layout.tsx              # 根布局，提供全局樣式與字體
│   │   │   ├── page.tsx                # 首頁（可能為重定向至登入頁）
│   │   │   ├── globals.css             # 全局樣式
│   │   │   ├── providers.tsx           # 全局 Provider 設定
│   │   │   ├── auth/                   # 認證相關頁面
│   │   │   │   ├── layout.tsx          # 認證頁面共用布局
│   │   │   │   ├── signin/            # 登入頁面資料夾
│   │   │   │   │   └── page.tsx       # 登入頁面
│   │   │   │   └── error/             # 錯誤處理頁面資料夾
│   │   │   │       └── page.tsx       # 錯誤頁面
│   │   │   ├── api/                   # API 路由
│   │   │   │   └── auth/              # 認證相關 API
│   │   │   │       └── [...nextauth]/
│   │   │   │           └── route.ts   # NextAuth 配置
│   │   │   └── dashboard/             # 儀表板與主要功能頁面
│   │   │       ├── layout.tsx         # 儀表板共用布局
│   │   │       ├── page.tsx           # 搜尋設定頁面
│   │   │       └── analysis/          # PDF 分析頁面
│   │   │           └── page.tsx
│   │   ├── types/                     # TypeScript 型別定義
│   │   │   ├── next-auth.d.ts        # NextAuth 型別擴充
│   │   │   └── next-themes.d.ts      # 主題相關型別定義
│   │   ├── lib/                       # 工具函式庫
│   │   │   ├── auth.ts               # 認證相關函式
│   │   │   └── utils.ts              # 通用工具函式
│   │   └── components/               # React 元件
│   │       ├── ui/                   # UI 元件
│   │       └── auth/                 # 認證相關元件
│   ├── package.json                  # 前端依賴配置
│   ├── next.config.ts               # Next.js 配置
│   ├── tailwind.config.ts           # Tailwind CSS 配置
│   ├── postcss.config.mjs           # PostCSS 配置
│   └── .env.local                   # 前端環境變數
│
├── backend/                         # 後端專案目錄 (FastAPI)
│   ├── requirements.txt             # Python 依賴清單
│   ├── .env                        # 後端環境變數
│   ├── app/                        # FastAPI 應用程式
│   │   ├── main.py                # 應用程式入口點
│   │   └── config.py              # 配置檔案
│   ├── routes/                    # API 路由
│   │   ├── auth.py               # 認證相關路由
│   │   ├── email.py              # 郵件處理路由
│   │   └── pdf.py                # PDF 處理路由
│   ├── services/                 # 主要業務邏輯
│   │   ├── auth.py              # 認證服務
│   │   ├── email.py             # 郵件服務
│   │   └── pdf.py               # PDF 處理服務
│   ├── models/                  # 資料模型
│   │   ├── user.py             # 使用者模型
│   │   └── pdf.py              # PDF 相關模型
│   ├── utils/                  # 工具函式
│   │   ├── pdf.py             # PDF 處理工具
│   │   └── email.py           # 郵件處理工具
│   ├── tests/                 # 測試目錄
│   │   ├── conftest.py       # 共用測試 fixtures 與測試資料
│   │   ├── unit/            # 單元測試
│   │   │   └── test_pdf_service.py  # PDF 服務測試
│   │   └── integration/     # 整合測試
│   │       └── test_pdf_workflow.py  # PDF 工作流程測試
│
└── docker/                   # Docker 相關配置
    ├── docker-compose.yml    # 容器編排配置
    ├── Dockerfile.frontend   # 前端容器配置
    └── Dockerfile.backend    # 後端容器配置
```

## 專案目錄結構概覽

### 根目錄
- `README.md`：專案概覽、安裝與使用說明
- `.env`：環境變數設定檔（OAuth、API Keys）
- `.gitignore`：Git 忽略檔案設定

### 文件 (docs/)
- `prd.md`：產品需求文件
- `API doc.md`：API 文件
- `FileStructure.md`：本文件
- `cursorrules.md`：開發規範

### 前端 (Next.js/TypeScript)
- `frontend/`
  - `package.json`：前端依賴配置
  - `next.config.ts`：Next.js 配置
  - `tailwind.config.ts`：Tailwind CSS 配置
  - `postcss.config.mjs`：PostCSS 配置
  - `.env.local`：前端環境變數
  - `src/`
    - `app/`：Next.js App Router 目錄
      - `layout.tsx`：根布局
      - `page.tsx`：首頁
      - `auth/`：認證相關頁面
      - `dashboard/`：主要功能頁面
    - `components/`：共用元件
    - `lib/`：工具函式
    - `types/`：TypeScript 型別定義

### 後端 (FastAPI)
- `backend/`
  - `requirements.txt`：Python 依賴清單
  - `.env`：後端環境變數
  - `app/`：FastAPI 應用程式
  - `routes/`：API 路由
  - `services/`：業務邏輯
  - `models/`：資料模型
  - `utils/`：工具函式
  - `tests/`：測試目錄
    - `conftest.py`：共用測試設定
    - `unit/`：單元測試
    - `integration/`：整合測試

### Docker 設定
- `docker/`
  - `docker-compose.yml`：容器編排配置
  - `Dockerfile.frontend`：前端容器配置
  - `Dockerfile.backend`：後端容器配置

## 重要檔案說明

### 前端 (Next.js/TypeScript)
- `next-auth.d.ts`: NextAuth 型別定義，包含 Session、User 和 JWT 介面
- `providers.tsx`: 全局 Provider 配置，包含認證和主題設定
- `[...nextauth]/route.ts`: NextAuth 路由配置，處理 OAuth 認證流程
- `analysis/page.tsx`: PDF 分析頁面，處理檔案上傳和分析結果顯示

### 後端 (FastAPI/Python)
- `auth.py`: 處理 OAuth 認證和 token 驗證
- `pdf.py`: PDF 檔案解析和資料提取
- `email.py`: 郵件處理和附件下載
- `conftest.py`: 測試環境配置和共用測試資料
- `test_pdf_service.py`: PDF 服務單元測試
- `test_pdf_workflow.py`: PDF 處理流程整合測試

### Docker 配置
- `docker-compose.yml`: 開發環境容器配置
- `Dockerfile.frontend`: 前端建置和執行環境
- `Dockerfile.backend`: 後端建置和執行環境
