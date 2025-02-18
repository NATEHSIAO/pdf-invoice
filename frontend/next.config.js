/** @type {import('next').NextConfig} */
const nextConfig = {
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'Content-Security-Policy',
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self' http://localhost:8000 http://backend:8000 https://accounts.google.com https://www.googleapis.com https://login.microsoftonline.com"
          }
        ],
      }
    ]
  },
  async rewrites() {
    return [
      {
        source: '/api/auth/:path*',
        destination: '/api/auth/:path*'
      },
      {
        source: '/api/:path*',
        destination: 'http://backend:8000/api/:path*'
      }
    ]
  },
  env: {
    NEXTAUTH_URL: process.env.NEXTAUTH_URL,
    NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET,
    NEXT_PUBLIC_GOOGLE_CLIENT_ID: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
    NEXT_PUBLIC_MICROSOFT_CLIENT_ID: process.env.NEXT_PUBLIC_MICROSOFT_CLIENT_ID
  },
  transpilePackages: ['antd', 'jszip'],
  webpack: (config) => {
    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
      path: false,
      stream: false,
      constants: false,
      zlib: false
    };
    return config;
  },
  experimental: {
    esmExternals: 'loose'
  },
  output: 'standalone',
}

module.exports = nextConfig 