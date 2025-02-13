import "next-auth"
import "next-auth/jwt"
import type { DefaultSession, DefaultUser } from "next-auth"
import type { DefaultJWT } from "next-auth/jwt"

declare module "next-auth" {
  /**
   * 擴展 Session 型別
   * @extends DefaultSession
   */
  interface Session {
    user: {
      id: string
      name: string | null
      email: string | null
      image: string | null
      accessToken: string
    }
  }

  /**
   * 擴展 User 型別
   * @extends DefaultUser
   */
  interface User {
    id: string
    name: string | null
    email: string | null
    image: string | null
  }

  /**
   * OAuth 帳戶資訊
   */
  interface Account {
    provider: string
    type: string
    providerAccountId: string
    access_token: string
    expires_at?: number
    scope?: string
    token_type?: string
    id_token?: string
  }
}

declare module "next-auth/jwt" {
  /**
   * 擴展 JWT 型別
   * @extends DefaultJWT
   */
  interface JWT {
    sub: string
    accessToken: string
    name: string | null
    email: string | null
    picture: string | null
  }
} 