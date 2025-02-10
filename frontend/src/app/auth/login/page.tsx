"use client"

import Image from "next/image"
import { getOAuthUrl } from "@/lib/auth"

export default function LoginPage() {
  const handleGoogleLogin = () => {
    window.location.href = getOAuthUrl("GOOGLE")
  }

  const handleMicrosoftLogin = () => {
    window.location.href = getOAuthUrl("MICROSOFT")
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-900 p-4">
      <div className="w-full max-w-md space-y-8 rounded-2xl bg-white p-8 shadow-lg dark:bg-zinc-800">
        <div className="flex flex-col items-center space-y-2 text-center">
          <div className="flex items-center space-x-2">
            <Image
              src="/logo.svg"
              alt="PDF Invoice Manager Logo"
              width={40}
              height={40}
              className="dark:invert"
            />
            <h1 className="text-2xl font-bold tracking-tight">
              PDF Invoice Manager
            </h1>
          </div>
          <p className="text-sm text-muted-foreground">
            請選擇以下方式登入
          </p>
        </div>
        <div className="grid gap-4">
          <button
            onClick={handleGoogleLogin}
            className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 px-4 py-2"
          >
            <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            使用 Google 帳號登入
          </button>
          <button
            onClick={handleMicrosoftLogin}
            className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 px-4 py-2"
          >
            <svg className="mr-2 h-4 w-4" viewBox="0 0 23 23">
              <path fill="#f25022" d="M1 1h10v10H1z"/>
              <path fill="#00a4ef" d="M1 12h10v10H1z"/>
              <path fill="#7fba00" d="M12 1h10v10H12z"/>
              <path fill="#ffb900" d="M12 12h10v10H12z"/>
            </svg>
            使用 Microsoft 帳號登入
          </button>
        </div>
        <p className="px-8 text-center text-sm text-muted-foreground">
          點擊登入即表示您同意我們的{" "}
          <a
            href="/terms"
            className="underline underline-offset-4 hover:text-primary"
          >
            服務條款
          </a>{" "}
          和{" "}
          <a
            href="/privacy"
            className="underline underline-offset-4 hover:text-primary"
          >
            隱私政策
          </a>
          。
        </p>
      </div>
    </div>
  )
} 