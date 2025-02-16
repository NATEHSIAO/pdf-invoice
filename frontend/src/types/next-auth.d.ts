import "next-auth"
import "next-auth/jwt"
import type { DefaultSession } from "next-auth"
import type { DefaultJWT } from "next-auth/jwt"

declare module "next-auth" {
  /**
   * 擴展 Session 型別
   * @extends DefaultSession
   */
  interface Session extends DefaultSession {
    user: {
      id: string
      name: string | null
      email: string
      image: string | null
      accessToken: string
      provider: string
      emailVerified: Date | null
    }
    expires: string
  }

  /**
   * 擴展 User 型別
   */
  interface User {
    id: string
    name?: string | null
    email?: string
    image?: string | null
    provider?: string
    emailVerified?: Date | null
  }

  /**
   * 擴展 Account 型別
   */
  interface Account {
    provider: string
    type: string
    providerAccountId: string
    access_token: string
    expires_at?: number
    refresh_token?: string | null
    scope: string
    token_type: string
    id_token?: string
  }
}

declare module "next-auth/jwt" {
  /**
   * 擴展 JWT 型別
   * @extends DefaultJWT
   */
  interface JWT extends DefaultJWT {
    id: string
    accessToken: string
    refreshToken: string | null
    provider: string
    name: string | null
    email: string
    picture: string | null
    emailVerified: Date | null
    sub: string
    iat?: number
    exp?: number
    jti: string
  }
} 