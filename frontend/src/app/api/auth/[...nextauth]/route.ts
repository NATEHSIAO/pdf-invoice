import NextAuth from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'
import MicrosoftProvider from 'next-auth/providers/azure-ad'
import type { NextAuthOptions } from 'next-auth'
import type { JWT } from 'next-auth/jwt'
import type { Session } from 'next-auth'
import type { Profile } from 'next-auth'

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      authorization: {
        params: {
          prompt: "consent",
          access_type: "offline",
          response_type: "code",
          scope: "openid email profile https://www.googleapis.com/auth/gmail.readonly"
        }
      }
    }),
    MicrosoftProvider({
      clientId: process.env.NEXT_PUBLIC_MICROSOFT_CLIENT_ID!,
      clientSecret: process.env.MICROSOFT_CLIENT_SECRET!,
      tenantId: 'common',
      authorization: {
        params: {
          scope: "openid profile email offline_access Mail.Read",
          prompt: "consent",
          response_mode: "query"
        }
      }
    })
  ],
  pages: {
    signIn: '/auth/login',
    error: '/auth/error',
    signOut: '/auth/signout'
  },
  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60 // 30 days
  },
  secret: process.env.NEXTAUTH_SECRET,
  debug: true,
  callbacks: {
    async signIn({ account, profile }: { account: any, profile?: Profile }) {
      if (!profile?.email) return false
      return true
    },
    async session({ session, token }: { session: Session, token: JWT }) {
      if (token && session.user) {
        session.user.id = token.sub || ''
        session.user.accessToken = token.accessToken as string
        session.user.provider = token.provider as string
        session.user.email = token.email as string
        session.user.image = token.picture as string
        session.user.emailVerified = new Date()
      }
      return session
    },
    async jwt({ token, account }) {
      if (account) {
        token.accessToken = account.access_token
        token.provider = account.provider
      }
      return token
    }
  }
}

const handler = NextAuth(authOptions)
export { handler as GET, handler as POST }
