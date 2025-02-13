import NextAuth from "next-auth"
import type { NextAuthConfig } from "next-auth"
import AzureADProvider from "next-auth/providers/azure-ad"

export const authOptions: NextAuthConfig = {
  providers: [
    AzureADProvider({
      clientId: process.env.AZURE_AD_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
      authorization: { params: { scope: "openid profile email" } }
    }),
  ],
  callbacks: {
    async jwt({ token, account, user }) {
      if (account && user) {
        if (!user.id) throw new Error("User ID is required")
        if (!account.access_token) throw new Error("Access token is required")
        
        token.accessToken = account.access_token
        token.name = user.name || null
        token.email = user.email || null
        token.picture = user.image || null
        token.sub = user.id
      }
      return token
    },
    async session({ session, token }) {
      if (!token.sub || !token.accessToken) {
        throw new Error("Invalid token")
      }
      
      return {
        ...session,
        user: {
          id: token.sub,
          name: token.name,
          email: token.email,
          image: token.picture,
          accessToken: token.accessToken
        }
      }
    },
  },
  pages: {
    signIn: "/auth/signin",
    error: "/auth/error",
  },
}

const handler = NextAuth(authOptions)
export { handler as GET, handler as POST } 