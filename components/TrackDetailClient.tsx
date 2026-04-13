"use client";

import { useState } from "react";
import Link from "next/link";
import type { Track } from "@/lib/utils";
import { yearsAgo, formatDateJa } from "@/lib/utils";
import { Jacket } from "@/components/Jacket";
import { SvcGrid } from "@/components/SvcLinks";
import { gaEvent } from "@/components/GoogleAnalytics";

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
    <div style={{ maxWidth: 600, margin: "0 auto", padding: "24px 20px 60px" }}>

      {/* 戻るリンク */}
      <Link
        href={`/date/${mmdd}`}
        style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--text-sec)", fontSize: "0.78rem", marginBottom: 24, textDecoration: "none" }}
      >
        ← {month}月{day}日のリリース一覧
      </Link>

      {/* ジャケット：約2/3幅・中央寄せ */}
      <div style={{ width: "66%", margin: "0 auto 24px", borderRadius: 12, overflow: "hidden" }}>
        <Jacket jacket={track.jacket} title={track.title} fullWidth />
      </div>

      {/* タイトル・アーティスト・リリース日：中央寄せ */}
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.4rem, 6vw, 2.2rem)",
            fontWeight: 700,
            color: "var(--text-pri)",
            lineHeight: 1.2,
            marginBottom: 12,
          }}
        >
          {track.title}
        </h1>
        <Link
          href={`/artist/${encodeURIComponent(track.artist)}`}
          style={{ fontSize: "1rem", color: "var(--text-sec)", fontWeight: 600, marginBottom: 10, display: "block", textDecoration: "none" }}
        >
          {track.artist}
        </Link>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.78rem", color: "var(--text-mute)" }}>
            {formatDateJa(track.releaseDate)}
          </span>
          {years > 0 && (
            <span
              style={{
                fontSize: "0.74rem",
                color: "var(--gold)",
                background: "#c8a84b22",
                border: "1px solid #c8a84b44",
                padding: "2px 10px",
                borderRadius: 3,
                fontWeight: 700,
              }}
            >
              {years}年前
            </span>
          )}
        </div>
      </div>

      {/* 解説 */}
      {track.note && (
        <div style={{ padding: "20px 0", borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)", marginBottom: 24 }}>
          <p style={{ fontSize: "0.88rem", color: "var(--text-pri)", lineHeight: 1.9, opacity: 0.9 }}>
            {track.note}
          </p>
        </div>
      )}

      {/* 試聴・再生リンク */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: "0.68rem", color: "var(--text-mute)", letterSpacing: "0.1em", marginBottom: 14 }}>
          試聴・再生
        </div>
        <SvcGrid links={track.links} trackTitle={track.title} artist={track.artist} />
      </div>

      {/* シェア */}
      <div style={{ paddingTop: 20, borderTop: "1px solid var(--border)", marginBottom: 32 }}>
        <div style={{ fontSize: "0.68rem", color: "var(--text-mute)", letterSpacing: "0.1em", marginBottom: 14 }}>
          シェア
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <ShareBtn onClick={shareX}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.747l7.73-8.835L1.254 2.25H8.08l4.261 5.636 5.903-5.636zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
            </svg>
            X でシェア
          </ShareBtn>
          <ShareBtn onClick={shareThreads}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.03-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.18 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-.505-1.808-1.343-3.233-2.487-4.234-1.19-1.036-2.868-1.587-4.9-1.6-2.832.019-4.952.965-6.475 2.898-1.426 1.806-2.168 4.298-2.196 7.405.028 3.11.77 5.6 2.196 7.405 1.522 1.93 3.64 2.876 6.467 2.895 2.256-.028 3.9-.605 5.072-1.744 1.346-1.31 1.895-3.256 1.895-5.457 0-.144-.005-.287-.016-.43h-7.019v-2.016h9.115c.028.29.044.585.044.883 0 2.9-.74 5.406-2.41 7.03C17.42 23.278 15.127 24 12.186 24z" />
            </svg>
            Threads でシェア
          </ShareBtn>
        </div>
      </div>

      {/* 同じ日の他の楽曲 */}
      {siblings.length > 0 && (
        <div>
          <div style={{ fontSize: "0.92rem", fontWeight: 700, color: "var(--text-pri)", marginBottom: 16 }}>
            {month}月{day}日にリリースされた他の楽曲
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {siblings.map((sib, i, arr) => {
              const year = sib.releaseDate.split("-")[0];
              const prevYear = arr[i - 1]?.releaseDate.split("-")[0];
              const currentYear = new Date().getFullYear();
              return (
                <div key={sib.id}>
                  {year !== prevYear && (
                    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 0 8px" }}>
                      <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-mute)", letterSpacing: "0.1em" }}>
                        {year}
                      </span>
                      <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
                      <span style={{ fontSize: "0.66rem", color: "var(--gold)" }}>
                        {currentYear - parseInt(year)}年前
                      </span>
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
  const [hov, setHov] = useState(false);

  return (
    <Link
      href={`/track/${track.id}`}
      style={{ textDecoration: "none" }}
      onClick={() => gaEvent("view_track", { track_id: track.id, track_title: track.title, artist: track.artist })}
    >
      <div
        onMouseEnter={() => setHov(true)}
        onMouseLeave={() => setHov(false)}
        style={{
          background: hov ? "var(--surface2)" : "var(--surface1)",
          borderRadius: 8,
          padding: "12px 14px",
          display: "flex",
          alignItems: "center",
          gap: 12,
          transition: "background 0.15s",
          animation: `fadeUp 0.3s ease both`,
          animationDelay: `${index * 60}ms`,
        }}
      >
        <Jacket jacket={track.jacket} title={track.title} size={48} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: "0.88rem", fontWeight: 700, color: "var(--text-pri)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {track.title}
          </div>
          <div style={{ fontSize: "0.76rem", color: "var(--text-sec)", marginTop: 3 }}>
            {track.artist}
          </div>
        </div>
        <span style={{ color: "var(--text-mute)", fontSize: "0.9rem", flexShrink: 0 }}>›</span>
      </div>
    </Link>
  );
}

// ── シェアボタン ──────────────────────────────────────────────

function ShareBtn({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  const [hov, setHov] = useState(false);

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: "8px 14px",
        borderRadius: 4,
        border: "1px solid var(--border)",
        background: hov ? "var(--surface2)" : "transparent",
        color: "var(--text-sec)",
        fontSize: "0.8rem",
        cursor: "pointer",
        fontFamily: "inherit",
        transition: "background 0.15s",
      }}
    >
      {children}
    </button>
  );
}
