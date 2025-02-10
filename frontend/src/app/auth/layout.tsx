import { Metadata } from "next"

export const metadata: Metadata = {
  title: "認證 - PDF Invoice Manager",
  description: "PDF Invoice Manager 認證系統",
}

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen">
      {children}
    </div>
  )
} 