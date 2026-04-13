import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/SiteHeader";

export const metadata: Metadata = {
  title: "プライバシーポリシー",
  description: "Release Tuneのプライバシーポリシーです。",
};

export default function PrivacyPage() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <SiteHeader />
      <div style={{ maxWidth: 680, margin: "0 auto", padding: "40px 20px 80px" }}>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: "1.6rem", fontWeight: 700, color: "var(--text-pri)", marginBottom: 8 }}>
          プライバシーポリシー
        </h1>
        <p style={{ fontSize: "0.78rem", color: "var(--text-mute)", marginBottom: 40 }}>最終更新日：2026年4月</p>
        <Section title="1. 基本方針">
          <p>ReleaseTune運営事務局（以下「当サービス」）は、ユーザーの個人情報の保護を重要な責務と認識し、適切な取り扱いに努めます。</p>
        </Section>
        <Section title="2. 収集する情報">
          <p>当サービスでは、以下の情報を収集することがあります。</p>
          <ul><li>アクセスログ（IPアドレス、ブラウザ情報、閲覧ページ、参照元URLなど）</li><li>Google Analyticsによるアクセス解析データ（Cookieを通じた匿名の行動情報）</li></ul>
          <p>当サービスは、氏名・メールアドレス・電話番号などの個人を直接特定できる情報を収集しません。</p>
        </Section>
        <Section title="3. 情報の利用目的">
          <p>収集した情報は以下の目的に限り利用します。</p>
          <ul><li>サービスの改善・機能向上</li><li>アクセス状況の把握・分析</li><li>不正アクセスの検知・防止</li></ul>
        </Section>
        <Section title="4. Google Analytics について">
          <p>当サービスはGoogleが提供するアクセス解析ツール「Google Analytics」を使用しています。Google Analyticsはトラフィックデータの収集のためにCookieを使用します。このトラフィックデータは匿名で収集されており、個人を特定するものではありません。</p>
          <p>Cookieを無効にすることでデータ収集を拒否できます。詳細は<a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer" style={{ color: "var(--gold)" }}>Googleのプライバシーポリシー</a>をご参照ください。</p>
        </Section>
        <Section title="5. 外部サービスへのリンクについて">
          <p>当サービスにはApple Music・Spotify・Amazon Music・YouTubeなどの外部サービスへのリンクが含まれています。これらの外部サービスにおける個人情報の取り扱いについては、各サービスのプライバシーポリシーをご確認ください。</p>
        </Section>
        <Section title="6. Cookieの使用について">
          <p>当サービスはGoogle AnalyticsのためにCookieを使用しています。Cookieはブラウザの設定から無効にすることができますが、一部の機能が利用できなくなる場合があります。</p>
        </Section>
        <Section title="7. プライバシーポリシーの変更">
          <p>当サービスは必要に応じて本プライバシーポリシーを変更することがあります。変更後のポリシーは本ページに掲載した時点から効力を生じます。</p>
        </Section>
        <Section title="8. お問い合わせ">
          <p>プライバシーに関するお問い合わせは、X（旧Twitter）アカウント <a href="https://x.com/releasetune" target="_blank" rel="noopener noreferrer" style={{ color: "var(--gold)" }}>@releasetune</a> のダイレクトメッセージにてお受けします。</p>
        </Section>
        <div style={{ marginTop: 48, paddingTop: 24, borderTop: "1px solid var(--border)" }}>
          <Link href="/" style={{ fontSize: "0.8rem", color: "var(--text-mute)", textDecoration: "none" }}>← トップページに戻る</Link>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 36 }}>
      <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1rem", fontWeight: 700, color: "var(--text-pri)", marginBottom: 12, paddingBottom: 8, borderBottom: "1px solid var(--border)" }}>{title}</h2>
      <div style={{ fontSize: "0.88rem", color: "var(--text-sec)", lineHeight: 1.9, display: "flex", flexDirection: "column", gap: 10 }}>{children}</div>
    </section>
  );
}
