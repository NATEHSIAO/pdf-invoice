"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { PaperclipIcon, X, LogOut } from "lucide-react"
import { format } from "date-fns"
import { zhTW } from "date-fns/locale"
import { useSession, signOut } from "next-auth/react"

interface EmailSender {
  name: string
  email: string
}

interface Attachment {
  filename: string
  mime_type: string
  size: number
}

interface Email {
  id: string
  subject: string
  sender: EmailSender
  date: string
  content: string
  hasAttachments: boolean
  attachments: Attachment[]
}

interface APIEmail {
  id: string
  subject: string
  sender: {
    name: string
    email: string
  }
  date: string
  content: string
  has_attachments: boolean
  attachments: Array<{
    filename: string
    mimeType: string
    size: number
  }>
}

export default function DashboardPage() {
  const router = useRouter()
  const { data: session, status } = useSession()
  const [searchKeywords, setSearchKeywords] = useState<string>("發票")
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
    end: new Date().toISOString().split("T")[0],
  })
  const [folder, setFolder] = useState<string>("INBOX")
  const [emails, setEmails] = useState<Email[]>([])
  const [selectedEmails, setSelectedEmails] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null)

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/auth/login")
    }
  }, [status, router])

  const getProviderForAPI = (provider?: string) => {
    if (!provider) return "GOOGLE";
    
    // 將 AZURE-AD 對應到 MICROSOFT
    if (provider.toUpperCase() === "AZURE-AD") {
      return "MICROSOFT";
    }
    
    return provider.toUpperCase();
  };

  const handleSearch = async () => {
    setIsLoading(true)
    try {
      const accessToken = session?.user?.accessToken
      if (!accessToken) {
        console.error("找不到存取令牌")
        router.push("/auth/login")
        return
      }

      const searchParamsPayload = {
        provider: getProviderForAPI(session?.user?.provider),
        keywords: searchKeywords,
        dateRange: {
          start: dateRange.start,
          end: dateRange.end
        },
        folder,
      }
      
      console.log("搜尋參數:", JSON.stringify(searchParamsPayload, null, 2))

      const response = await fetch("/api/emails/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${accessToken}`
        },
        body: JSON.stringify(searchParamsPayload)
      })

      console.log("搜尋響應狀態:", response.status)
      
      if (!response.ok) {
        if (response.status === 401) {
          console.log("認證失敗，導向登入頁")
          signOut({ callbackUrl: "/auth/login" })
          return
        }
        throw new Error("搜尋時發生錯誤")
      }

      const data = await response.json()
      
      const formattedEmails = (data as APIEmail[]).map((email: APIEmail) => ({
        id: email.id,
        subject: email.subject || "（無主旨）",
        sender: {
          name: email.sender?.name || "未知寄件者",
          email: email.sender?.email || ""
        },
        date: email.date,
        content: email.content || "",
        hasAttachments: email.has_attachments || false,
        attachments: email.attachments?.map(att => ({
          filename: att.filename,
          mime_type: att.mimeType,
          size: att.size
        })) || []
      }))

      setEmails(formattedEmails)
      setSelectedEmails(new Set(formattedEmails.map(email => email.id)))
    } catch (error) {
      console.error("搜尋錯誤:", error)
      alert(error instanceof Error ? error.message : "搜尋時發生錯誤")
    } finally {
      setIsLoading(false)
    }
  }

  const handleSelectAll = () => {
    if (selectedEmails.size === emails.length) {
      setSelectedEmails(new Set())
    } else {
      setSelectedEmails(new Set(emails.map(email => email.id)))
    }
  }

  const handleSelectEmail = (emailId: string) => {
    const newSelected = new Set(selectedEmails)
    if (newSelected.has(emailId)) {
      newSelected.delete(emailId)
    } else {
      newSelected.add(emailId)
    }
    setSelectedEmails(newSelected)
  }

  const handleStartAnalysis = () => {
    if (selectedEmails.size === 0) return
    router.push(`/dashboard/analysis?emails=${Array.from(selectedEmails).join(",")}`)
  }

  const handleLogout = () => {
    signOut({ callbackUrl: "/auth/login" })
  }

  const formatFileSize = (bytes: number): string => {
    const units = ['B', 'KB', 'MB', 'GB']
    let size = bytes
    let unitIndex = 0
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024
      unitIndex++
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`
  }

  return (
    <div className="container mx-auto p-4 space-y-6">
      <div className="rounded-lg border p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">搜尋條件</h2>
          <button
            onClick={handleLogout}
            className="flex items-center text-sm text-muted-foreground hover:text-foreground"
          >
            <LogOut className="h-4 w-4 mr-1" />
            登出
          </button>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">關鍵字</label>
            <input
              type="text"
              value={searchKeywords}
              onChange={(e) => setSearchKeywords(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-black"
              placeholder="輸入搜尋關鍵字"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">起始日期</label>
            <input
              type="date"
              value={dateRange.start}
              onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
              className="w-full rounded-md border px-3 py-2 text-black"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">結束日期</label>
            <input
              type="date"
              value={dateRange.end}
              onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
              className="w-full rounded-md border px-3 py-2 text-black"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">信件夾</label>
            <select
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-black"
            >
              <option value="INBOX">收件匣</option>
              <option value="ARCHIVE">封存</option>
            </select>
          </div>
        </div>
        <button
          onClick={handleSearch}
          disabled={isLoading}
          className="rounded-md bg-primary px-4 py-2 text-white hover:bg-primary/90 disabled:opacity-50 border border-primary"
        >
          {isLoading ? "搜尋中..." : "開始搜尋"}
        </button>
      </div>

      <div className="rounded-lg border">
        <div className="border-b p-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <input
              type="checkbox"
              checked={selectedEmails.size === emails.length && emails.length > 0}
              onChange={handleSelectAll}
              className="rounded border-gray-300"
            />
            <span className="text-sm text-muted-foreground">
              已選擇 {selectedEmails.size} 封郵件
            </span>
            <button
              onClick={handleStartAnalysis}
              disabled={selectedEmails.size === 0}
              className="rounded-md bg-primary px-4 py-2 text-white hover:bg-primary/90 disabled:opacity-50 border border-primary"
            >
              開始解析
            </button>
          </div>
        </div>
        <div className="divide-y">
          {emails.map((email) => (
            <div 
              key={email.id} 
              className="flex items-center p-4 hover:bg-muted/50 cursor-pointer"
              onClick={() => setSelectedEmail(email)}
            >
              <input
                type="checkbox"
                checked={selectedEmails.has(email.id)}
                onChange={(e) => {
                  e.stopPropagation()
                  handleSelectEmail(email.id)
                }}
                className="mr-4 rounded border-gray-300"
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <p className="truncate font-medium">{email.subject}</p>
                    {email.hasAttachments && (
                      <PaperclipIcon className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                  <p className="ml-4 flex-shrink-0 text-sm text-muted-foreground">
                    {format(new Date(email.date), "yyyy/MM/dd HH:mm", { locale: zhTW })}
                  </p>
                </div>
                <p className="truncate text-sm text-muted-foreground">
                  {email.sender.name} &lt;{email.sender.email}&gt;
                </p>
              </div>
            </div>
          ))}
          {emails.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              {isLoading ? "搜尋中..." : "尚無搜尋結果"}
            </div>
          )}
        </div>
      </div>

      {/* 郵件內容抽屜 */}
      {selectedEmail && (
        <div className="fixed inset-y-0 right-0 w-1/3 bg-background border-l shadow-lg transform transition-transform">
          <div className="h-full flex flex-col">
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="text-lg font-semibold">郵件內容</h3>
              <button
                onClick={() => setSelectedEmail(null)}
                className="p-2 hover:bg-muted rounded-full"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4 space-y-4">
              <div>
                <p className="font-medium">{selectedEmail.sender.name}</p>
                <p className="text-sm text-muted-foreground">{selectedEmail.sender.email}</p>
              </div>
              <div>
                <p className="font-medium">主旨</p>
                <p className="text-sm">{selectedEmail.subject}</p>
              </div>
              <div>
                <p className="font-medium">日期</p>
                <p className="text-sm">
                  {format(new Date(selectedEmail.date), "yyyy/MM/dd HH:mm", { locale: zhTW })}
                </p>
              </div>
              <div>
                <p className="font-medium">內容</p>
                <div className="mt-2 text-sm whitespace-pre-wrap">
                  {selectedEmail.content}
                </div>
              </div>
              {selectedEmail.attachments.length > 0 && (
                <div>
                  <p className="font-medium mb-2">附件</p>
                  <div className="space-y-2">
                    {selectedEmail.attachments.map((attachment, index) => (
                      <div
                        key={index}
                        className="flex items-center space-x-2 p-2 rounded-md border"
                      >
                        <PaperclipIcon className="h-4 w-4 text-muted-foreground" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm truncate">{attachment.filename}</p>
                          <p className="text-xs text-muted-foreground">
                            {attachment.mime_type} • {formatFileSize(attachment.size)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
} 