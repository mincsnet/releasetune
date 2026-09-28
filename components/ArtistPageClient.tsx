"use client";

import Link from "next/link";
import type { Track } from "@/lib/utils";
import type { DebutInfo } from "@/lib/tracks";
import { formatDateJa } from "@/lib/utils";
import { Jacket } from "@/components/Jacket";
import { TrackSvcLinks } from "@/components/SvcLinks";
import { gaEvent } from "@/components/GoogleAnalytics";
import styles from "./ArtistPageClient.module.css";

interface ArtistSummary {
  name: string;
  trackCount: number;
  jacket: string;
  tracks: (Track & { mmdd: string })[];
}

interface Props {
  artist: ArtistSummary;
  debutInfo?: DebutInfo | null;
}

export function ArtistPageClient({ artist, debutInfo }: Props) {
  const { name, trackCount, jacket, tracks } = artist;

  return (
    <div className={styles.page}>

      {/* アーティストヒーロー */}
      <div className={styles.hero}>
        {/* 代表ジャケット */}
        <div className={styles.avatar}>
          {jacket ? (
            <Jacket jacket={jacket} title={name} size={120} />
          ) : (
            <div className={styles.avatarFallback}>♪</div>
          )}
        </div>

        <div>
          <h1 className={styles.name}>{name}</h1>

          {debutInfo && (
            <div className={styles.debut}>
              <span className={styles.debutLabel}>デビュー</span>
              {" "}{debutInfo.debutDate.replace(/-/g, ".")}
              {debutInfo.debutTrack && (
                <span className={styles.debutTrack}>「{debutInfo.debutTrack}」</span>
              )}
            </div>
          )}

          <div className={styles.count}>{trackCount} TRACKS</div>
        </div>
      </div>

      {/* 楽曲一覧 */}
      <div className={styles.tracks}>
        <div className={styles.tracksHeading}>リリース楽曲一覧</div>

        <div className={styles.list}>
          {tracks.map((track, i, arr) => {
            const year = track.releaseDate.split("-")[0];
            const prevYear = arr[i - 1]?.releaseDate.split("-")[0];
            const currentYear = new Date().getFullYear();
            return (
              <div key={track.id} className={styles.listItem}>
                {year !== prevYear && (
                  <div className={styles.yearHeader}>
                    <span className={styles.yearLabel}>{year}</span>
                    <div className={styles.yearRule} />
                    <span className={styles.yearAgo}>{currentYear - parseInt(year)}年前</span>
                  </div>
                )}
                <ArtistTrackCard track={track} index={i} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── トラックカード ──────────────────────────────────────────────

function ArtistTrackCard({ track, index }: { track: Track & { mmdd: string }; index: number }) {
  const [month, day] = track.mmdd.split("-").map(Number);

  return (
    <div className={styles.card} style={{ animationDelay: `${Math.min(index * 40, 600)}ms` }}>
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
        {/* リリース日と日付ページへのリンク */}
        <Link href={`/date/${track.mmdd}`} className={styles.plainLink}>
          <div className={styles.cardDate}>
            {formatDateJa(track.releaseDate)}
            <span className={styles.cardDateLink}>{month}月{day}日のリリース →</span>
          </div>
        </Link>
        <TrackSvcLinks links={track.links} trackTitle={track.title} artist={track.artist} />
      </div>
    </div>
  );
}
