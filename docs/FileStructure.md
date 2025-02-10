# FileStructure.md

## 專案目錄結構

```
.
├── README.md                # 專案概覽、安裝與使用說明
├── .gitignore              # Git 忽略檔案設定
├── .env                    # 環境變數設定檔（OAuth、API Keys）
│
├── frontend/              # 前端專案目錄
│   ├── public/           # 靜態資源
│   │   ├── logo.svg     # 應用程式 logo
│   │   └── ...
│   ├── src/
│   │   ├── app/         # Next.js App Router 目錄
│   │   │   ├── layout.tsx              # 根布局，提供全局樣式和字體
│   │   │   ├── page.tsx                # 首頁（重定向到登入）
│   │   │   ├── globals.css             # 全局樣式
│   │   │   └── auth/                   # 認證相關頁面
│   │   │       ├── layout.tsx          # 認證頁面共用布局
│   │   │       ├── login/
│   │   │       │   └── page.tsx        # 登入頁面
│   │   │       └── callback/
│   │   │           └── [provider]/
│   │   │               └── page.tsx     # OAuth 回調頁面
│   │   ├── lib/         # 工具函式庫
│   │   │   ├── auth.ts  # 認證相關函式
│   │   │   └── utils.ts # 通用工具函式
│   │   └── types/       # TypeScript 型別定義
│   ├── package.json     # 前端依賴配置
│   ├── next.config.ts   # Next.js 配置
│   ├── tailwind.config.ts # Tailwind CSS 配置
│   ├── postcss.config.mjs # PostCSS 配置
│   └── .env.local      # 前端環境變數
│
├── backend/             # 後端專案目錄
│   ├── app/            # FastAPI 應用程式
│   │   ├── main.py     # 應用程式入口
│   │   └── config.py   # 配置檔案
│   ├── routes/         # API 路由
│   │   ├── auth.py     # 認證相關路由
│   │   ├── email.py    # 郵件處理路由
│   │   └── pdf.py      # PDF 處理路由
│   ├── services/       # 業務邏輯
│   │   ├── auth.py     # 認證服務
│   │   ├── email.py    # 郵件服務
│   │   └── pdf.py      # PDF 處理服務
│   ├── models/         # 資料模型
│   │   ├── user.py     # 使用者模型
│   │   └── pdf.py      # PDF 相關模型
│   ├── utils/          # 工具函式
│   │   ├── pdf.py      # PDF 處理工具
│   │   └── email.py    # 郵件處理工具
│   ├── requirements.txt # Python 依賴清單
│   └── .env            # 後端環境變數
│
└── docker/             # Docker 相關配置
    ├── docker-compose.yml    # 容器編排配置
    ├── Dockerfile.frontend   # 前端容器配置
    └── Dockerfile.backend    # 後端容器配置
```

## 專案目錄結構概覽

- **根目錄**
  - `README.md`：專案概覽、安裝與使用說明
  - `.env`：環境變數設定檔（OAuth、API Keys）
  - `.gitignore`：Git 忽略檔案設定

- **前端 (Next.js/TypeScript)**
  - `frontend/`
    - `package.json`：前端依賴配置
    - `next.config.js`：Next.js 配置
    - `tailwind.config.js`：Tailwind CSS 配置
    - `postcss.config.js`：PostCSS 配置
    - `.env.local`：前端環境變數
    - `src/`
      - `app/`：Next.js App Router 目錄
        - `layout.tsx`：根布局
        - `page.tsx`：首頁
        - `auth/`：認證相關頁面
          - `login/page.tsx`：登入頁面
          - `callback/page.tsx`：OAuth 回調頁面
        - `dashboard/`：主要功能頁面
          - `page.tsx`：搜尋設定頁面
          - `analysis/page.tsx`：發票解析頁面
      - `components/`：共用元件
        - `ui/`：UI 元件
        - `auth/`：認證相關元件
        - `dashboard/`：儀表板相關元件
      - `lib/`：工具函式
        - `utils.ts`：通用工具函式
        - `auth.ts`：認證相關函式
      - `types/`：TypeScript 型別定義

- **後端 (FastAPI)**
  - `backend/`
    - `requirements.txt`：Python 依賴清單
    - `.env`：後端環境變數
    - `app/`
      - `main.py`：應用程式入口
      - `config.py`：配置檔案
    - `routes/`：API 路由
      - `auth.py`：認證相關路由
      - `email.py`：郵件處理路由
      - `pdf.py`：PDF 處理路由
    - `services/`：業務邏輯
      - `auth.py`：認證服務
      - `email.py`：郵件服務
      - `pdf.py`：PDF 處理服務
    - `models/`：資料模型
      - `user.py`：使用者模型
      - `pdf.py`：PDF 相關模型
    - `utils/`：工具函式
      - `pdf.py`：PDF 處理工具
      - `email.py`：郵件處理工具

- **Docker 設定**
  - `docker/`
    - `docker-compose.yml`：容器編排配置
    - `Dockerfile.frontend`：前端容器配置
    - `Dockerfile.backend`：後端容器配置

- **文件**
  - `docs/`
    - `prd.md`：產品需求文件
    - `API doc.md`：API 文件
    - `FileStructure.md`：本文件
    - `cursorrules.md`：開發規範
