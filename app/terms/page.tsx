import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/SiteHeader";

export const metadata: Metadata = {
  title: "利用規約",
  description: "Release Tuneの利用規約です。",
};

export default function TermsPage() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <SiteHeader />
      <div style={{ maxWidth: 680, margin: "0 auto", padding: "40px 20px 80px" }}>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: "1.6rem", fontWeight: 700, color: "var(--text-pri)", marginBottom: 8 }}>
          利用規約
        </h1>
        <p style={{ fontSize: "0.78rem", color: "var(--text-mute)", marginBottom: 40 }}>最終更新日：2026年4月</p>
        <Section title="1. はじめに">
          <p>本利用規約（以下「本規約」）は、ReleaseTune運営事務局（以下「当サービス」）が提供するウェブサービス「Release Tune」の利用条件を定めるものです。ユーザーは本サービスを利用することで、本規約に同意したものとみなします。</p>
        </Section>
        <Section title="2. サービスの概要">
          <p>本サービスは、指定した日付にリリースされた音楽作品の情報を提供するウェブサービスです。表示される楽曲情報・ジャケット画像・各音楽配信サービスへのリンクは、Apple iTunes Search API等の公開APIを通じて取得・表示しています。</p>
          <p>本サービスは情報提供を目的としており、音楽の販売・配信は行っておりません。</p>
        </Section>
        <Section title="3. 知的財産権">
          <p>本サービスに表示される楽曲タイトル・アーティスト名・ジャケット画像等の著作権・商標権は、各権利者（レコード会社・アーティスト・Apple Inc.等）に帰属します。</p>
          <p>ジャケット画像はApple iTunes Search APIより提供されるものであり、各Apple Musicコンテンツへのリンクと組み合わせて表示しています。</p>
          <p>本サービスのシステム・デザイン・コードに関する権利は当サービスに帰属します。</p>
        </Section>
        <Section title="4. 免責事項">
          <p>当サービスは以下の事項について責任を負いません。</p>
          <ul>
            <li>表示される楽曲情報（リリース日・アーティスト名・タイトル等）の正確性・完全性</li>
            <li>外部の音楽配信サービスの仕様変更・サービス終了によるリンク切れや機能停止</li>
            <li>本サービスの利用によって生じた損害</li>
            <li>本サービスの一時的な停止・終了</li>
          </ul>
        </Section>
        <Section title="5. 禁止事項">
          <p>ユーザーは以下の行為を行ってはなりません。</p>
          <ul>
            <li>本サービスのデータを無断で大量収集・転載・二次利用する行為</li>
            <li>本サービスのシステムに過度な負荷をかける行為</li>
            <li>本サービスの運営を妨害する行為</li>
            <li>その他、法令または公序良俗に反する行為</li>
          </ul>
        </Section>
        <Section title="6. 外部サービスについて">
          <p>本サービスに掲載されているApple Music・Spotify・Amazon Music・YouTubeへのリンクは、各サービスの利用規約に従ってご利用ください。これらの外部サービスの利用に関して、当サービスは一切の責任を負いません。</p>
          <p>Music data provided by Apple Music / iTunes.</p>
        </Section>
        <Section title="7. 規約の変更">
          <p>当サービスは必要に応じて本規約を変更することがあります。変更後の規約は本ページに掲載した時点から効力を生じます。重要な変更がある場合はX（@releasetune）にてお知らせします。</p>
        </Section>
        <Section title="8. お問い合わせ">
          <p>本規約に関するお問い合わせは、X（旧Twitter）アカウント <a href="https://x.com/releasetune" target="_blank" rel="noopener noreferrer" style={{ color: "var(--gold)" }}>@releasetune</a> のダイレクトメッセージにてお受けします。</p>
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
