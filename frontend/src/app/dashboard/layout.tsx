"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(true)

  console.log("DashboardLayout 開始渲染")

  useEffect(() => {
    console.log("DashboardLayout useEffect 執行")
    const checkAuth = async () => {
      try {
        const access_token = localStorage.getItem("access_token")
        console.log("access_token 狀態:", access_token ? "存在" : "不存在")
        
        if (!access_token) {
          console.log("無 access token，重導向到登入頁")
          router.push("/auth/login")
          return
        }
        
        setIsLoading(false)
      } catch (error) {
        console.error("驗證檢查失敗:", error)
        router.push("/auth/login")
      }
    }

    checkAuth()
  }, [router])

  if (isLoading) {
    console.log("DashboardLayout 載入中")
    return <div>載入中...</div>
  }

  console.log("DashboardLayout 渲染子組件")
  return (
    <div className="min-h-screen">
      {children}
    </div>
  )
} 