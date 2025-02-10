/** @type {import('next').NextConfig} */
const nextConfig = {
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: `
              default-src 'self';
              script-src 'self' 'unsafe-inline' https://accounts.google.com https://apis.google.com;
              style-src 'self' 'unsafe-inline' https://accounts.google.com;
              img-src 'self' data: https: https://accounts.google.com https://*.googleusercontent.com;
              font-src 'self' data:;
              connect-src 'self' http://localhost:8000 http://backend:8000 https://accounts.google.com https://oauth2.googleapis.com https://www.googleapis.com https://login.microsoftonline.com https://graph.microsoft.com;
              frame-src 'self' https://accounts.google.com https://login.microsoftonline.com;
              form-action 'self' https://accounts.google.com https://login.microsoftonline.com;
            `.replace(/\s+/g, ' ').trim()
          }
        ]
      }
    ]
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://backend:8000/api/:path*'
      }
    ]
  }
}

module.exports = nextConfig 