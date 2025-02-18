"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { ArrowLeft, Download, FileDown, Loader2, LogOut } from "lucide-react"
import { format } from "date-fns"
import { zhTW } from "date-fns/locale"
import { useSession, signOut } from "next-auth/react"
import type { Session } from "next-auth"
import JSZip from "jszip"
import { message } from "antd"

interface InvoiceData {
  email_subject: string
  email_sender: string
  email_date: string
  invoice_number: string
  invoice_date: string
  buyer_name: string
  buyer_tax_id: string
  seller_name: string
  taxable_amount: number
  tax_free_amount: number
  zero_tax_amount: number
  tax_amount: number
  total_amount: number
}

interface AnalysisProgress {
  total: number
  current: number
  status: string
  message: string
}

interface AnalysisResult {
  invoices: InvoiceData[]
  failed_files: string[]
  download_url: string | null
}

// IndexedDB 相關常數
const DB_NAME = 'PDFInvoiceDB';
const STORE_NAME = 'pdfs';
const DB_VERSION = 2;  // 增加版本號以觸發資料庫升級

interface PDFRecord {
  filename: string;
  content: string;
  sessionId: string;
  createdAt: number;
}

// 修改 initDB 的實作
const initDB = async (): Promise<IDBDatabase> => {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event: IDBVersionChangeEvent) => {
      const db = (event.target as IDBOpenDBRequest).result;
      
      // 如果存儲區已存在，則刪除它
      if (db.objectStoreNames.contains(STORE_NAME)) {
        db.deleteObjectStore(STORE_NAME);
      }
      
      // 創建新的存儲區
      const store = db.createObjectStore(STORE_NAME, { 
        keyPath: ['sessionId', 'filename']
      });
      
      // 創建索引
      store.createIndex('sessionId', 'sessionId', { unique: false });
      store.createIndex('createdAt', 'createdAt', { unique: false });
      
      console.log('資料庫升級完成，已創建所需索引');
    };
  });
};

// 修改 clearSessionPDFs 函數
const clearSessionPDFs = async (sessionId: string): Promise<void> => {
  console.log('開始清理 session PDFs:', sessionId);
  const db = await initDB();
  return new Promise<void>((resolve, reject) => {
    try {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const sessionIndex = store.index('sessionId');
      const request = sessionIndex.openCursor(IDBKeyRange.only(sessionId));

      const deletePromises: Promise<void>[] = [];

      request.onerror = () => {
        console.error('清理 PDFs 時發生錯誤:', request.error);
        reject(request.error);
      };

      request.onsuccess = (event: Event) => {
        const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
        if (cursor) {
          deletePromises.push(
            new Promise<void>((res, rej) => {
              const deleteRequest = cursor.delete();
              deleteRequest.onerror = () => rej(deleteRequest.error);
              deleteRequest.onsuccess = () => res();
            })
          );
          cursor.continue();
        } else {
          Promise.all(deletePromises)
            .then(() => {
              console.log('成功清理 session PDFs');
              resolve();
            })
            .catch(error => {
              console.error('清理 PDFs 時發生錯誤:', error);
              reject(error);
            });
        }
      };
    } catch (error) {
      console.error('執行清理操作時發生錯誤:', error);
      reject(error);
    }
  });
};

// 修改 savePDFToIndexedDB 函數
const savePDFToIndexedDB = async (sessionId: string, filename: string, content: string) => {
  const db = await initDB();
  return new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const record: PDFRecord = {
      filename,
      content,
      sessionId,
      createdAt: Date.now()
    };
    const request = store.put(record);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
};

// 修改 getSessionPDFs 函數
const getSessionPDFs = async (sessionId: string): Promise<PDFRecord[]> => {
  console.log('開始獲取 session PDFs:', sessionId);
  const db = await initDB();
  return new Promise<PDFRecord[]>((resolve, reject) => {
    try {
      const transaction = db.transaction(STORE_NAME, 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const sessionIndex = store.index('sessionId');
      const request = sessionIndex.getAll(IDBKeyRange.only(sessionId));

      request.onerror = () => {
        console.error('獲取 PDFs 時發生錯誤:', request.error);
        reject(request.error);
      };

      request.onsuccess = () => {
        console.log('成功獲取 PDFs，數量:', request.result.length);
        resolve(request.result);
      };
    } catch (error) {
      console.error('執行獲取操作時發生錯誤:', error);
      reject(error);
    }
  });
};

// 修改 cleanupOldPDFs 函數
const cleanupOldPDFs = async (maxAgeHours = 24): Promise<void> => {
  console.log('開始清理過期 PDFs');
  const db = await initDB();
  const cutoffTime = Date.now() - (maxAgeHours * 60 * 60 * 1000);
  
  return new Promise<void>((resolve, reject) => {
    try {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const createdAtIndex = store.index('createdAt');
      const request = createdAtIndex.openCursor(IDBKeyRange.upperBound(cutoffTime));

      const deletePromises: Promise<void>[] = [];

      request.onerror = () => {
        console.error('清理過期 PDFs 時發生錯誤:', request.error);
        reject(request.error);
      };

      request.onsuccess = (event: Event) => {
        const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
        if (cursor) {
          deletePromises.push(
            new Promise<void>((res, rej) => {
              const deleteRequest = cursor.delete();
              deleteRequest.onerror = () => rej(deleteRequest.error);
              deleteRequest.onsuccess = () => res();
            })
          );
          cursor.continue();
        } else {
          Promise.all(deletePromises)
            .then(() => {
              console.log('成功清理過期 PDFs');
              resolve();
            })
            .catch(error => {
              console.error('清理過期 PDFs 時發生錯誤:', error);
              reject(error);
            });
        }
      };
    } catch (error) {
      console.error('執行清理過期操作時發生錯誤:', error);
      reject(error);
    }
  });
};

function AnalysisContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { data: session, status } = useSession()
  const [isAnalyzing, setIsAnalyzing] = useState(true)
  const [progress, setProgress] = useState<AnalysisProgress | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [currentSessionId, setCurrentSessionId] = useState<string>('')

  useEffect(() => {
    // 生成新的 session ID
    setCurrentSessionId(crypto.randomUUID())
    
    // 清理過期的 PDF
    cleanupOldPDFs().catch(console.error)
  }, [])

  useEffect(() => {
    const emailIds = searchParams.get("emails")?.split(",") || []
    if (emailIds.length === 0) {
      router.push("/dashboard")
      return
    }

    const startAnalysis = async (emails: string[]) => {
      try {
        if (!session?.user?.accessToken) {
          console.error('未登入或未找到存取令牌')
          router.push("/auth/login")
          return
        }

        const response = await fetch(`/api/pdf/analyze`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${session.user.accessToken}`
          },
          body: JSON.stringify({ emails })
        })

        if (!response.ok) {
          throw new Error('解析失敗')
        }

        const result = await response.json()
        setResult(result)
        setIsAnalyzing(false)
      } catch (error) {
        console.error('解析錯誤:', error)
        setIsAnalyzing(false)
      }
    }

    startAnalysis(emailIds)
  }, [searchParams, router, session])

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (isAnalyzing) {
      // 開始輪詢進度
      intervalId = setInterval(async () => {
        try {
          const response = await fetch("/api/pdf/progress");
          const data = await response.json();
          setProgress(data);
          
          // 如果狀態是 completed 或 error，停止輪詢
          if (data.status === "completed" || data.status === "error") {
            setIsAnalyzing(false);
            clearInterval(intervalId);
          }
        } catch (error) {
          console.error("獲取進度時發生錯誤:", error);
          setIsAnalyzing(false);
          clearInterval(intervalId);
        }
      }, 1000);
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [isAnalyzing]);

  // 下載所有當前 session 的 PDF
  const handleDownloadPDFs = async () => {
    try {
      if (!currentSessionId) {
        message.error('無法識別當前工作階段')
        return
      }

      const pdfs = await getSessionPDFs(currentSessionId)
      if (!pdfs || pdfs.length === 0) {
        message.error('沒有可下載的 PDF 檔案')
        return
      }

      const zip = new JSZip()
      
      pdfs.forEach(({ filename, content }) => {
        zip.file(filename, content, { base64: true })
      })

      const content = await zip.generateAsync({ type: 'blob' })
      const url = window.URL.createObjectURL(content)
      const a = document.createElement('a')
      a.href = url
      a.download = `invoices_${format(new Date(), "yyyyMMdd_HHmmss")}.zip`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      message.success('PDF 下載完成')
    } catch (error) {
      console.error('下載 PDF 失敗:', error)
      message.error('下載 PDF 失敗')
    }
  }

  const handleLogout = async () => {
    if (currentSessionId) {
      await clearSessionPDFs(currentSessionId)
    }
    signOut({ callbackUrl: "/auth/login" })
  }

  const handleDownloadCSV = () => {
    if (!result?.invoices) return

    const headers = [
      "Email主旨",
      "寄件人",
      "Email日期",
      "發票號碼",
      "發票日期",
      "買受人",
      "統一編號",
      "開立單位",
      "應稅銷售額",
      "免稅銷售額",
      "零稅率銷售額",
      "營業稅稅額",
      "發票總金額",
    ]

    const rows = result.invoices.map((invoice) => [
      invoice.email_subject,
      invoice.email_sender,
      format(new Date(invoice.email_date), "yyyy/MM/dd HH:mm", { locale: zhTW }),
      invoice.invoice_number,
      invoice.invoice_date,
      invoice.buyer_name,
      invoice.buyer_tax_id,
      invoice.seller_name,
      invoice.taxable_amount,
      invoice.tax_free_amount,
      invoice.zero_tax_amount,
      invoice.tax_amount,
      invoice.total_amount,
    ])

    const csvContent = [
      headers.join(","),
      ...rows.map((row) => row.join(",")),
    ].join("\n")

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" })
    const link = document.createElement("a")
    link.href = URL.createObjectURL(blob)
    link.download = `發票彙整_${format(new Date(), "yyyyMMdd")}.csv`
    link.click()
  }

  const handleBackToSearch = async () => {
    if (currentSessionId) {
      await clearSessionPDFs(currentSessionId)
    }
    router.push('/dashboard')
  }

  // 組件卸載時清理當前 session 的資料
  useEffect(() => {
    return () => {
      if (currentSessionId) {
        clearSessionPDFs(currentSessionId).catch(console.error)
      }
    }
  }, [currentSessionId])

  return (
    <div className="container mx-auto p-4 space-y-6">
      <div className="flex items-center justify-between">
        <button
          onClick={handleBackToSearch}
          className="flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          返回搜尋
        </button>
        <div className="flex items-center space-x-4">
          <button
            onClick={handleLogout}
            className="flex items-center text-sm text-muted-foreground hover:text-foreground"
          >
            <LogOut className="h-4 w-4 mr-1" />
            登出
          </button>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleDownloadCSV}
              disabled={!result?.invoices}
              className="flex items-center rounded-md bg-primary px-4 py-2 text-sm text-white hover:bg-primary/90 disabled:opacity-50"
            >
              <FileDown className="h-4 w-4 mr-1" />
              下載 CSV
            </button>
            <button
              onClick={handleDownloadPDFs}
              disabled={isAnalyzing}
              className="flex items-center rounded-md border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50"
            >
              <Download className="h-4 w-4 mr-1" />
              下載 PDF
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-lg border p-8">
        {isAnalyzing ? (
          <div className="flex flex-col items-center justify-center space-y-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <div className="text-center">
              <p className="font-medium">資料解析中</p>
              {progress && (
                <div className="mt-2">
                  <div className="h-2 w-64 rounded-full bg-muted">
                    <div
                      className="h-2 rounded-full bg-primary transition-all"
                      style={{
                        width: `${(progress.current / progress.total) * 100}%`,
                      }}
                    />
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {progress.message} ({progress.current}/{progress.total})
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : result?.invoices && result.invoices.length > 0 ? (
          <div className="rounded-lg border">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="p-3 text-left text-sm font-medium">Email主旨</th>
                    <th className="p-3 text-left text-sm font-medium">寄件人</th>
                    <th className="p-3 text-left text-sm font-medium">Email日期</th>
                    <th className="p-3 text-left text-sm font-medium">發票號碼</th>
                    <th className="p-3 text-left text-sm font-medium">發票日期</th>
                    <th className="p-3 text-left text-sm font-medium">買受人</th>
                    <th className="p-3 text-left text-sm font-medium">統一編號</th>
                    <th className="p-3 text-left text-sm font-medium">開立單位</th>
                    <th className="p-3 text-right text-sm font-medium">應稅銷售額</th>
                    <th className="p-3 text-right text-sm font-medium">免稅銷售額</th>
                    <th className="p-3 text-right text-sm font-medium">零稅率銷售額</th>
                    <th className="p-3 text-right text-sm font-medium">營業稅稅額</th>
                    <th className="p-3 text-right text-sm font-medium">發票總金額</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {result?.invoices?.map((invoice, index) => (
                    <tr key={index} className="hover:bg-muted/50">
                      <td className="p-3 text-sm">{invoice.email_subject}</td>
                      <td className="p-3 text-sm">{invoice.email_sender}</td>
                      <td className="p-3 text-sm">
                        {format(new Date(invoice.email_date), "yyyy/MM/dd HH:mm", {
                          locale: zhTW,
                        })}
                      </td>
                      <td className="p-3 text-sm">{invoice.invoice_number}</td>
                      <td className="p-3 text-sm">{invoice.invoice_date}</td>
                      <td className="p-3 text-sm">{invoice.buyer_name}</td>
                      <td className="p-3 text-sm">{invoice.buyer_tax_id}</td>
                      <td className="p-3 text-sm">{invoice.seller_name}</td>
                      <td className="p-3 text-sm text-right">
                        {invoice.taxable_amount.toLocaleString()}
                      </td>
                      <td className="p-3 text-sm text-right">
                        {invoice.tax_free_amount.toLocaleString()}
                      </td>
                      <td className="p-3 text-sm text-right">
                        {invoice.zero_tax_amount.toLocaleString()}
                      </td>
                      <td className="p-3 text-sm text-right">
                        {invoice.tax_amount.toLocaleString()}
                      </td>
                      <td className="p-3 text-sm text-right">
                        {invoice.total_amount.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border p-8 text-center text-muted-foreground">
            無法解析 PDF 文件
          </div>
        )}
      </div>

      {result?.failed_files && result.failed_files.length > 0 && (
        <div className="rounded-lg border p-4">
          <h3 className="font-medium mb-2">解析失敗的文件</h3>
          <ul className="space-y-1 text-sm text-muted-foreground">
            {result.failed_files.map((file, index) => (
              <li key={index}>{file}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default function AnalysisPage() {
  return (
    <Suspense fallback={
      <div className="container mx-auto p-4">
        <div className="rounded-lg border p-8">
          <div className="flex flex-col items-center justify-center space-y-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="font-medium">載入中...</p>
          </div>
        </div>
      </div>
    }>
      <AnalysisContent />
    </Suspense>
  )
} 