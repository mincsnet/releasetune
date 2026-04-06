import Link from "next/link";
import { getTodayMmdd } from "@/lib/tracks";

export default function NotFound() {
  const today = getTodayMmdd();

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--bg)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        gap: 16,
        padding: 20,
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: "3rem", color: "var(--text-mute)" }}>♪</div>
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "1.4rem",
          color: "var(--text-pri)",
        }}
      >
        ページが見つかりません
      </h1>
      <p style={{ fontSize: "0.84rem", color: "var(--text-sec)" }}>
        URLが正しいかご確認ください
      </p>
      <Link
        href={`/date/${today}`}
        style={{
          marginTop: 8,
          padding: "8px 20px",
          borderRadius: 4,
          border: "1px solid var(--gold)",
          color: "var(--gold)",
          textDecoration: "none",
          fontSize: "0.84rem",
          fontWeight: 600,
        }}
      >
        今日のリリースを見る
      </Link>
    </div>
  );
}
