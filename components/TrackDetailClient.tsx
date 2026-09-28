"use client";

import Link from "next/link";
import type { Track } from "@/lib/utils";
import { yearsAgo, formatDateJa } from "@/lib/utils";
import { Jacket } from "@/components/Jacket";
import { SvcGrid } from "@/components/SvcLinks";
import { gaEvent } from "@/components/GoogleAnalytics";
import styles from "./TrackDetailClient.module.css";

interface Props {
  track: Track;
  mmdd: string;
  month: number;
  day: number;
  siblings: Track[];
}

export function TrackDetailClient({ track, mmdd, month, day, siblings }: Props) {
  const years = yearsAgo(track.releaseDate);

  const shareText = `📅${formatDateJa(track.releaseDate)}リリース\n${track.artist}「${track.title}」${years > 0 ? `（${years}年前！）` : ""}\n\n#ReleaseTune\nhttps://releasetune.com/track/${track.id}`;

  function shareX() {
    gaEvent("share", { method: "X", track_title: track.title, artist: track.artist });
    window.open("https://x.com/intent/tweet?text=" + encodeURIComponent(shareText), "_blank");
  }

  function shareThreads() {
    gaEvent("share", { method: "Threads", track_title: track.title, artist: track.artist });
    window.open("https://www.threads.net/intent/post?text=" + encodeURIComponent(shareText), "_blank");
  }

  return (
    <div className={styles.page}>

      {/* 戻るリンク */}
      <Link href={`/date/${mmdd}`} className={styles.back}>
        ← {month}月{day}日のリリース一覧
      </Link>

      <div className={styles.hero}>
        <div className={styles.jacket}>
          <Jacket jacket={track.jacket} title={track.title} fullWidth />
        </div>

        <div>
          <div className={styles.head}>
            <h1 className={styles.title}>{track.title}</h1>
            <Link href={`/artist/${encodeURIComponent(track.artist)}`} className={styles.artist}>
              {track.artist}
            </Link>
            <div className={styles.meta}>
              <span className={styles.date}>{formatDateJa(track.releaseDate)}</span>
              {years > 0 && <span className={styles.yearsBadge}>{years}年前</span>}
            </div>
          </div>

          {/* 解説 */}
          {track.note && (
            <div className={styles.note}>
              <p className={styles.noteText}>{track.note}</p>
            </div>
          )}

          {/* 試聴・再生リンク */}
          <div className={styles.section}>
            <div className={styles.sectionLabel}>試聴・再生</div>
            <SvcGrid links={track.links} trackTitle={track.title} artist={track.artist} />
          </div>

          {/* YouTube埋め込み */}
          {track.links?.youtubeId && track.links?.youtubeVerified && (
            <div className={styles.section}>
              <div className={styles.mvLabel}>MV / 公式動画</div>
              <div className={styles.mvFrame}>
                <iframe
                  src={`https://www.youtube.com/embed/${track.links.youtubeId}?rel=0`}
                  title={`${track.title} - ${track.artist}`}
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                  className={styles.mvIframe}
                />
              </div>
            </div>
          )}

          {/* シェア */}
          <div className={styles.share}>
            <div className={styles.sectionLabel}>シェア</div>
            <div className={styles.shareBtns}>
              <button onClick={shareX} className={styles.shareBtn}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.747l7.73-8.835L1.254 2.25H8.08l4.261 5.636 5.903-5.636zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
                X でシェア
              </button>
              <button onClick={shareThreads} className={styles.shareBtn}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.03-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.18 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-.505-1.808-1.343-3.233-2.487-4.234-1.19-1.036-2.868-1.587-4.9-1.6-2.832.019-4.952.965-6.475 2.898-1.426 1.806-2.168 4.298-2.196 7.405.028 3.11.77 5.6 2.196 7.405 1.522 1.93 3.64 2.876 6.467 2.895 2.256-.028 3.9-.605 5.072-1.744 1.346-1.31 1.895-3.256 1.895-5.457 0-.144-.005-.287-.016-.43h-7.019v-2.016h9.115c.028.29.044.585.044.883 0 2.9-.74 5.406-2.41 7.03C17.42 23.278 15.127 24 12.186 24z" />
                </svg>
                Threads でシェア
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 同じ日の他の楽曲 */}
      {siblings.length > 0 && (
        <div className={styles.siblings}>
          <div className={styles.siblingsHeading}>
            {month}月{day}日にリリースされた他の楽曲
          </div>
          <div className={styles.siblingsList}>
            {siblings.map((sib, i, arr) => {
              const year = sib.releaseDate.split("-")[0];
              const prevYear = arr[i - 1]?.releaseDate.split("-")[0];
              const currentYear = new Date().getFullYear();
              return (
                <div key={sib.id} className={styles.siblingsItem}>
                  {year !== prevYear && (
                    <div className={styles.yearHeader}>
                      <span className={styles.yearLabel}>{year}</span>
                      <div className={styles.yearRule} />
                      <span className={styles.yearAgo}>{currentYear - parseInt(year)}年前</span>
                    </div>
                  )}
                  <SibCard track={sib} index={i} />
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── 兄弟トラックカード（コンパクト横並び） ────────────────────────

function SibCard({ track, index }: { track: Track; index: number }) {
  return (
    <Link
      href={`/track/${track.id}`}
      className={styles.sibLink}
      onClick={() => gaEvent("view_track", { track_id: track.id, track_title: track.title, artist: track.artist })}
    >
      <div className={styles.sib} style={{ animationDelay: `${index * 60}ms` }}>
        <Jacket jacket={track.jacket} title={track.title} size={48} />
        <div className={styles.sibBody}>
          <div className={styles.sibTitle}>{track.title}</div>
          <div className={styles.sibArtist}>{track.artist}</div>
        </div>
        <span className={styles.sibChevron}>›</span>
      </div>
    </Link>
  );
}
