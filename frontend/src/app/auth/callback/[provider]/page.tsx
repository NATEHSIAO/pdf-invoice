"use client"

import { use, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { handleOAuthCallback } from "@/lib/auth"
import { Loader2 } from "lucide-react"

export default function CallbackPage({
  params,
}: {
  params: Promise<{ provider: string }>
}) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const code = searchParams.get("code")
  const resolvedParams = use(params)

  useEffect(() => {
    async function handleCallback() {
      if (!code) {
        setError("未收到授權碼")
        setTimeout(() => router.push("/auth/login"), 3000)
        return
      }

      try {
        const provider = resolvedParams.provider.toUpperCase() as "GOOGLE" | "MICROSOFT"
        console.log("開始處理 OAuth 回調:", { provider, code })
        
        const result = await handleOAuthCallback(provider, code)
        
        if ('error' in result) {
          console.error("認證失敗:", result.error)
          setError(result.error)
          setTimeout(() => router.push("/auth/login"), 3000)
          return
        }
        
        console.log("認證成功，儲存 token")
        localStorage.setItem("access_token", result.access_token)
        router.push("/dashboard")
      } catch (error) {
        console.error("認證處理失敗:", error)
        setError(error instanceof Error ? error.message : "認證過程發生錯誤")
        setTimeout(() => router.push("/auth/login"), 3000)
      }
    }

    handleCallback()
  }, [code, resolvedParams.provider, router])

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-semibold mb-4 text-red-500">認證失敗</h2>
          <p className="text-muted-foreground mb-4">{error}</p>
          <p className="text-sm text-muted-foreground">3 秒後返回登入頁面...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-4" />
        <h2 className="text-2xl font-semibold mb-4">處理登入中...</h2>
        <p className="text-muted-foreground">請稍候，我們正在驗證您的身份</p>
      </div>
    </div>
  )
} 