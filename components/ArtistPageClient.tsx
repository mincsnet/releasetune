"use client";

import { useState } from "react";
import Link from "next/link";
import type { Track } from "@/lib/utils";
import type { DebutInfo } from "@/lib/tracks";
import { yearsAgo, formatDateJa } from "@/lib/utils";
import { Jacket } from "@/components/Jacket";
import { TrackSvcLinks } from "@/components/SvcLinks";
import { gaEvent } from "@/components/GoogleAnalytics";

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
    <div style={{ maxWidth: 600, margin: "0 auto", padding: "0 0 60px" }}>

      {/* アーティストヒーロー */}
      <div
        style={{
          background: "linear-gradient(180deg,#c8a84b22 0%,#c8a84b08 50%,#0f0f0f 100%)",
          padding: "28px 20px 24px",
          textAlign: "center",
        }}
      >
        {/* 代表ジャケット */}
        <div
          style={{
            width: 120,
            height: 120,
            borderRadius: 60,
            overflow: "hidden",
            margin: "0 auto 16px",
            border: "2px solid #c8a84b44",
          }}
        >
          {jacket ? (
            <Jacket jacket={jacket} title={name} size={120} />
          ) : (
            <div
              style={{
                width: 120,
                height: 120,
                background: "linear-gradient(135deg,#c8a84b33,#1a1a1a)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "2.5rem",
                color: "#c8a84b88",
              }}
            >
              ♪
            </div>
          )}
        </div>

        {/* アーティスト名 */}
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.4rem, 6vw, 2rem)",
            fontWeight: 700,
            color: "var(--text-pri)",
            marginBottom: 8,
          }}
        >
          {name}
        </h1>

        {/* デビュー情報 */}
        {debutInfo && (
          <div style={{ fontSize: "0.78rem", color: "var(--text-mute)", marginBottom: 6, lineHeight: 1.7 }}>
            <span style={{ color: "var(--gold)" }}>デビュー</span>
            {" "}{debutInfo.debutDate.replace(/-/g, ".")}
            {debutInfo.debutTrack && (
              <span style={{ marginLeft: 6 }}>「{debutInfo.debutTrack}」</span>
            )}
          </div>
        )}

        {/* 楽曲数 */}
        <div style={{ fontSize: "0.78rem", color: "var(--text-mute)", letterSpacing: "0.06em" }}>
          {trackCount} TRACKS
        </div>
      </div>

      {/* 楽曲一覧 */}
      <div style={{ padding: "0 20px" }}>
        <div
          style={{
            fontSize: "0.82rem",
            fontWeight: 700,
            color: "var(--text-pri)",
            padding: "20px 0 12px",
          }}
        >
          リリース楽曲一覧
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {tracks.map((track, i, arr) => {
            const year = track.releaseDate.split("-")[0];
            const prevYear = arr[i - 1]?.releaseDate.split("-")[0];
            const currentYear = new Date().getFullYear();
            return (
              <div key={track.id}>
                {year !== prevYear && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "12px 0 8px",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        color: "var(--text-mute)",
                        letterSpacing: "0.1em",
                      }}
                    >
                      {year}
                    </span>
                    <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
                    <span style={{ fontSize: "0.66rem", color: "var(--gold)" }}>
                      {currentYear - parseInt(year)}年前
                    </span>
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
  const [hov, setHov] = useState(false);
  const { month, day } = (() => {
    const [m, d] = track.mmdd.split("-").map(Number);
    return { month: m, day: d };
  })();

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? "var(--surface2)" : "var(--surface1)",
        borderRadius: 8,
        padding: 14,
        display: "grid",
        gridTemplateColumns: "60px 1fr",
        gap: 12,
        animation: `fadeUp 0.3s ease both`,
        animationDelay: `${Math.min(index * 40, 600)}ms`,
        transition: "background 0.15s",
      }}
    >
      <Link
        href={`/track/${track.id}`}
        onClick={() => gaEvent("view_track", { track_id: track.id, track_title: track.title, artist: track.artist })}
      >
        <Jacket jacket={track.jacket} title={track.title} size={60} />
      </Link>
      <div style={{ minWidth: 0 }}>
        <Link
          href={`/track/${track.id}`}
          style={{ textDecoration: "none" }}
          onClick={() => gaEvent("view_track", { track_id: track.id, track_title: track.title, artist: track.artist })}
        >
          <div
            style={{
              fontSize: "0.92rem",
              fontWeight: 700,
              color: "var(--text-pri)",
              lineHeight: 1.3,
              marginBottom: 3,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {track.title}
          </div>
        </Link>
        {/* リリース日と日付ページへのリンク */}
        <Link
          href={`/date/${track.mmdd}`}
          style={{ textDecoration: "none" }}
        >
          <div
            style={{
              fontSize: "0.72rem",
              color: "var(--text-mute)",
              marginBottom: 8,
            }}
          >
            {formatDateJa(track.releaseDate)}
            <span style={{ marginLeft: 6, color: "var(--gold)", fontSize: "0.66rem" }}>
              {month}月{day}日のリリース →
            </span>
          </div>
        </Link>
        <TrackSvcLinks links={track.links} trackTitle={track.title} artist={track.artist} />
      </div>
    </div>
  );
}
