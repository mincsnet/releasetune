import Link from "next/link";
import styles from "./SiteHeader.module.css";

export function SiteHeader() {
  return (
    <header className={styles.header}>
      <Link href="/" className={styles.logo}>
        <span className={styles.logoRelease}>Release</span>
        <span className={styles.logoTune}>Tune</span>
      </Link>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span className={styles.tagline}>今日はあの曲のリリース日</span>
        <Link
          href="/search"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 32,
            height: 32,
            borderRadius: 6,
            border: "1px solid var(--border)",
            color: "var(--text-mute)",
            textDecoration: "none",
            transition: "background 0.15s, color 0.15s",
          }}
          aria-label="楽曲・アーティストを検索"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </Link>
      </div>
    </header>
  );
}
