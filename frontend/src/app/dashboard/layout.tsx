"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useSession } from "next-auth/react"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { data: session, status } = useSession()
  const router = useRouter()

  console.log("DashboardLayout 開始渲染")

  useEffect(() => {
    console.log("DashboardLayout useEffect 執行")
    // 若狀態為 unauthenticated 則導向登入頁
    if (status === "unauthenticated") {
      console.log("無 access token，重導向到登入頁")
      router.push("/auth/login")
    }
  }, [status, router])

  if (status === "loading") {
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