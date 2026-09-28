"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import type { Track } from "@/lib/utils";
import { formatDateJa, yearsAgo } from "@/lib/utils";
import { Jacket } from "@/components/Jacket";
import { TrackSvcLinks } from "@/components/SvcLinks";
import { gaEvent } from "@/components/GoogleAnalytics";
import styles from "./SearchPageClient.module.css";

interface SearchResult extends Track {
  mmdd: string;
}

interface Props {
  query: string;
  results: SearchResult[];
}

export function SearchPageClient({ query, results }: Props) {
  const router = useRouter();
  const [input, setInput] = useState(query);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q) return;
    gaEvent("search", { search_term: q });
    startTransition(() => {
      router.push(`/search?q=${encodeURIComponent(q)}`);
    });
  }

  return (
    <div className={styles.page}>

      {/* 検索フォーム */}
      <form onSubmit={handleSubmit} className={styles.form}>
        <div className={styles.field}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-mute)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.fieldIcon}>
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="楽曲タイトル・アーティスト名で検索..."
            autoFocus
            className={styles.input}
          />
          <button
            type="submit"
            disabled={isPending || !input.trim()}
            className={`${styles.submit} ${input.trim() ? styles.submitActive : ""}`}
          >
            {isPending ? "検索中..." : "検索"}
          </button>
        </div>
      </form>

      {/* 結果表示 */}
      {query && (
        <>
          <div className={styles.summary}>
            {results.length > 0 ? (
              <>
                「<span className={styles.queryText}>{query}</span>」の検索結果：
                <span className={styles.resultCount}>{results.length} 件</span>
                {results.length >= 50 && (
                  <span className={styles.limitNote}>（上位50件を表示）</span>
                )}
              </>
            ) : (
              <>
                「<span className={styles.queryText}>{query}</span>」に一致する楽曲が見つかりませんでした
              </>
            )}
          </div>

          {results.length > 0 && (
            <div className={styles.list}>
              {results.map((track, i) => (
                <SearchResultCard key={track.id} track={track} index={i} />
              ))}
            </div>
          )}

          {results.length === 0 && (
            <div className={styles.placeholder}>
              <div className={styles.noneIcon}>♪</div>
              <div className={styles.noneTitle}>別のキーワードで試してみてください</div>
              <div className={styles.placeholderHint}>例：アーティスト名、楽曲タイトルの一部</div>
            </div>
          )}
        </>
      )}

      {/* 初期状態 */}
      {!query && (
        <div className={styles.placeholder}>
          <div className={styles.introIcon}>🎵</div>
          <div className={styles.introTitle}>楽曲タイトルやアーティスト名を入力してください</div>
          <div className={styles.placeholderHint}>32,000曲以上のデータから検索できます</div>
        </div>
      )}
    </div>
  );
}

// ── 検索結果カード ────────────────────────────────────────────

function SearchResultCard({ track, index }: { track: SearchResult; index: number }) {
  const years = yearsAgo(track.releaseDate);
  const [m, d] = track.mmdd.split("-").map(Number);

  return (
    <div className={styles.card} style={{ animationDelay: `${Math.min(index * 30, 400)}ms` }}>
      <Link
        href={`/track/${track.id}`}
        onClick={() => gaEvent("view_track", { track_id: track.id, track_title: track.title, artist: track.artist })}
      >
        <Jacket jacket={track.jacket} title={track.title} size={60} />
      </Link>
      <div className={styles.cardBody}>
        <Link
          href={`/track/${track.id}`}
          className={styles.plainLink}
          onClick={() => gaEvent("view_track", { track_id: track.id, track_title: track.title, artist: track.artist })}
        >
          <div className={styles.cardTitle}>{track.title}</div>
        </Link>
        <Link href={`/artist/${encodeURIComponent(track.artist)}`} className={styles.plainLink}>
          <div className={styles.cardArtist}>{track.artist}</div>
        </Link>
        <div className={styles.cardMeta}>
          <span className={styles.cardDate}>{formatDateJa(track.releaseDate)}</span>
          {years > 0 && <span className={styles.yearsBadge}>{years}年前</span>}
          <Link href={`/date/${track.mmdd}`} className={styles.plainLink}>
            <span className={styles.cardDateLink}>{m}月{d}日のリリース →</span>
          </Link>
        </div>
        <TrackSvcLinks links={track.links} trackTitle={track.title} artist={track.artist} />
      </div>
    </div>
  );
}
