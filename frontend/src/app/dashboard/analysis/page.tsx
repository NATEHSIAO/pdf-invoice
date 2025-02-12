"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { ArrowLeft, Download, FileDown, Loader2, LogOut } from "lucide-react"
import { format } from "date-fns"
import { zhTW } from "date-fns/locale"

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

function AnalysisContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [isAnalyzing, setIsAnalyzing] = useState(true)
  const [progress, setProgress] = useState<AnalysisProgress | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)

  useEffect(() => {
    const emailIds = searchParams.get("emails")?.split(",") || []
    if (emailIds.length === 0) {
      router.push("/dashboard")
      return
    }

    const startAnalysis = async () => {
      try {
        const access_token = localStorage.getItem("access_token")
        if (!access_token) {
          router.push("/auth/login")
          return
        }

        const response = await fetch("/api/pdf/analyze", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${access_token}`
          },
          body: JSON.stringify(emailIds),
        })

        if (!response.ok) {
          if (response.status === 401) {
            router.push("/auth/login")
            return
          }
          throw new Error("解析失敗")
        }

        const data = await response.json()
        setResult(data)
        setIsAnalyzing(false)
      } catch (error) {
        console.error("解析錯誤:", error)
        setIsAnalyzing(false)
      }
    }

    const pollProgress = async () => {
      try {
        const response = await fetch("/api/pdf/progress")
        if (response.ok) {
          const data = await response.json()
          setProgress(data)
          if (data.status === "processing") {
            setTimeout(pollProgress, 1000)
          }
        }
      } catch (error) {
        console.error("獲取進度失敗:", error)
      }
    }

    startAnalysis()
    pollProgress()
  }, [searchParams, router])

  const handleLogout = () => {
    localStorage.removeItem("access_token")
    router.push("/auth/login")
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

  const handleDownloadPDFs = () => {
    if (!result?.download_url) return
    window.location.href = result.download_url
  }

  return (
    <div className="container mx-auto p-4 space-y-6">
      <div className="flex items-center justify-between">
        <button
          onClick={() => router.push("/dashboard")}
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
              disabled={!result?.download_url}
              className="flex items-center rounded-md border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50"
            >
              <Download className="h-4 w-4 mr-1" />
              下載 PDF
            </button>
          </div>
        </div>
      </div>

      {isAnalyzing ? (
        <div className="rounded-lg border p-8">
          <div className="flex flex-col items-center justify-center space-y-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <div className="text-center">
              <p className="font-medium">正在解析 PDF 文件</p>
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
        </div>
      ) : result?.invoices ? (
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
                {result.invoices.map((invoice, index) => (
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