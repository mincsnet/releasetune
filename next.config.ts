import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "is1-ssl.mzstatic.com" },
      { protocol: "https", hostname: "is2-ssl.mzstatic.com" },
      { protocol: "https", hostname: "is3-ssl.mzstatic.com" },
      { protocol: "https", hostname: "is4-ssl.mzstatic.com" },
      { protocol: "https", hostname: "is5-ssl.mzstatic.com" },
      { protocol: "https", hostname: "i.scdn.co" },
      { protocol: "https", hostname: "*.mzstatic.com" },
    ],
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          // クリックジャッキング防止
          { key: "X-Frame-Options", value: "DENY" },
          // MIMEタイプスニッフィング防止
          { key: "X-Content-Type-Options", value: "nosniff" },
          // リファラー情報を制限
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // 許可する外部リソースを明示（CSP）
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.googletagmanager.com https://www.youtube.com",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: https://*.mzstatic.com https://i.scdn.co https://img.youtube.com https://www.googletagmanager.com",
              "frame-src https://www.youtube.com",
              "connect-src 'self' https://*.supabase.co https://www.google-analytics.com https://region1.google-analytics.com",
            ].join("; "),
          },
          // HTTPS強制（Vercelは自動でHTTPSだが念のため）
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
          // 権限ポリシー（不要なブラウザ機能を無効化）
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
