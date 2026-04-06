import Link from "next/link";
import { getTodayMmdd } from "@/lib/tracks";
import styles from "./SiteHeader.module.css";

export function SiteHeader() {
  const today = getTodayMmdd();

  return (
    <header className={styles.header}>
      <Link href={`/date/${today}`} className={styles.logo}>
        <span className={styles.logoRelease}>Release</span>
        <span className={styles.logoTune}>Tune</span>
      </Link>
      <span className={styles.tagline}>今日はあの曲のリリース日</span>
    </header>
  );
}
