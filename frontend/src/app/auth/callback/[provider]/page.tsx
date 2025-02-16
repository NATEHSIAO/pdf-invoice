"use client"

import { useEffect } from "react"
import { signIn } from "next-auth/react"
import { useRouter, useSearchParams } from "next/navigation"

export default function CallbackPage({
  params,
}: {
  params: { provider: string }
}) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const code = searchParams.get("code")
  const error = searchParams.get("error")

  useEffect(() => {
    if (error) {
      console.error("認證錯誤:", error)
      router.push("/auth/login")
      return
    }

    if (!code) {
      router.push("/auth/login")
      return
    }

    // 直接使用 NextAuth 的內建處理方式
    signIn(params.provider.toLowerCase(), {
      callbackUrl: "/dashboard",
      redirect: true
    })
  }, [code, error, params.provider, router])

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-center">
        <p>處理登入中，請稍候...</p>
      </div>
    </div>
  )
} 