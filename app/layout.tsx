import type { Metadata } from "next";
import { Noto_Sans_JP, Zen_Old_Mincho } from "next/font/google";
import "./globals.css";
import { GoogleAnalytics } from "@/components/GoogleAnalytics";

const notoSansJP = Noto_Sans_JP({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-noto",
  display: "swap",
});

const zenOldMincho = Zen_Old_Mincho({
  subsets: ["latin"],
  weight: ["700"],
  variable: "--font-zen",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Release Tune — 今日はあの曲のリリース日",
    template: "%s — Release Tune",
  },
  description: "今日この日にリリースされた楽曲を、年代を超えてご紹介します。",
  metadataBase: new URL("https://releasetune.com"),
  openGraph: {
    siteName: "Release Tune",
    type: "website",
    locale: "ja_JP",
  },
  twitter: {
    card: "summary_large_image",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja" className={`${notoSansJP.variable} ${zenOldMincho.variable}`}>
      <body>
        <GoogleAnalytics gaId="G-3SDZ478Y78" />
        {children}
      </body>
    </html>
  );
}
