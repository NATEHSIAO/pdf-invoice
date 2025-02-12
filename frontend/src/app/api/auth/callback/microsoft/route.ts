import { NextRequest } from 'next/server';
import { handleOAuthCallback } from '@/lib/auth';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const error = searchParams.get('error');
  const baseUrl = request.nextUrl.origin;

  if (error) {
    console.error('Microsoft OAuth 錯誤:', error);
    return Response.redirect(`${baseUrl}/auth/error?error=${encodeURIComponent(error)}`);
  }

  if (!code) {
    console.error('未收到授權碼');
    return Response.redirect(`${baseUrl}/auth/error?error=未收到授權碼`);
  }

  try {
    const response = await handleOAuthCallback('MICROSOFT', code);
    if ('error' in response) {
      console.error('處理回調錯誤:', response.error);
      return Response.redirect(`${baseUrl}/auth/error?error=${encodeURIComponent(response.error)}`);
    }

    // 成功登入，重定向到首頁
    return Response.redirect(`${baseUrl}/`);
  } catch (error) {
    console.error('回調處理失敗:', error);
    return Response.redirect(`${baseUrl}/auth/error?error=${encodeURIComponent(String(error))}`);
  }
} 