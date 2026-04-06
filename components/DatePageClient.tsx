"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import type { Track } from "@/lib/utils";
import { yearsAgo, formatDateJa, parseMmdd } from "@/lib/utils";
import { Jacket } from "@/components/Jacket";
import { SvcGrid, TrackSvcLinks } from "@/components/SvcLinks";
import { gaEvent } from "@/components/GoogleAnalytics";

interface Props {
  mmdd: string;
  tracks: Track[];
  today: string;
}

export function DatePageClient({ mmdd, tracks, today }: Props) {
  const router = useRouter();
  const { month, day } = parseMmdd(mmdd);
  const isToday = mmdd === today;

  const featuredIdx = useMemo(
    () => (tracks.length > 0 ? Math.floor(Math.random() * tracks.length) : 0),
    [tracks.length]
  );
  const featured = tracks.length > 0 ? tracks[featuredIdx] : null;
  const others = tracks.filter((t) => t.id !== featured?.id);

  function shiftDate(delta: number) {
    const [m, d] = mmdd.split("-").map(Number);
    const base = new Date(2024, m - 1, d + delta);
    const next = `${String(base.getMonth() + 1).padStart(2, "0")}-${String(base.getDate()).padStart(2, "0")}`;
    gaEvent("navigate_date", { date: next });
    router.push(`/date/${next}`);
  }

  return (
    <>
      {/* ヒーローエリア */}
      <div
        style={{
          background:
            "linear-gradient(180deg,#c8a84b22 0%,#c8a84b0a 40%,#0f0f0f 100%)",
          padding: "32px 20px 24px",
          textAlign: "center",
        }}
      >
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(2rem, 7vw, 3rem)",
            fontWeight: 700,
            color: "var(--text-pri)",
            lineHeight: 1.1,
            marginBottom: 8,
          }}
        >
          {month}月{day}日
        </h1>
        <p
          style={{
            fontSize: "0.74rem",
            color: "var(--text-mute)",
            letterSpacing: "0.08em",
          }}
        >
          ON THIS DAY
        </p>
      </div>

      {/* 日付ナビゲーション */}
      <div
        style={{
          maxWidth: 600,
          margin: "0 auto",
          padding: "0 20px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          flexWrap: "wrap",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <NavBtn onClick={() => shiftDate(-1)}>◀ 前日</NavBtn>
        <div
          style={{
            background: "var(--surface1)",
            border: "1px solid var(--border)",
            borderRadius: 4,
            padding: "5px 18px",
            fontFamily: "var(--font-display)",
            fontSize: "1rem",
            fontWeight: 700,
            color: "var(--text-pri)",
            minWidth: 90,
            textAlign: "center",
          }}
        >
          {month}月{day}日
        </div>
        <NavBtn onClick={() => shiftDate(1)}>翌日 ▶</NavBtn>
        {!isToday && (
          <NavBtn onClick={() => router.push(`/date/${today}`)} accent>
            今日に戻る
          </NavBtn>
        )}
      </div>

      {/* コンテンツ */}
      <div
        style={{
          maxWidth: 600,
          margin: "0 auto",
          padding: "0 20px 60px",
        }}
      >
        {tracks.length > 0 ? (
          <>
            {/* フィーチャード楽曲 */}
            {featured && (
              <div
                style={{
                  padding: "24px 0",
                  borderBottom: "1px solid var(--border)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    gap: 20,
                    alignItems: "flex-end",
                    marginBottom: 16,
                  }}
                >
                  <Link href={`/track/${featured.id}`} style={{ flexShrink: 0 }}>
                    <Jacket jacket={featured.jacket} title={featured.title} size={120} />
                  </Link>
                  <div style={{ minWidth: 0, paddingBottom: 4 }}>
                    <Link
                      href={`/track/${featured.id}`}
                      style={{ textDecoration: "none" }}
                      onClick={() =>
                        gaEvent("view_track", {
                          track_id: featured.id,
                          track_title: featured.title,
                          artist: featured.artist,
                        })
                      }
                    >
                      <h2
                        style={{
                          fontFamily: "var(--font-display)",
                          fontSize: "clamp(1.1rem, 4vw, 1.6rem)",
                          fontWeight: 700,
                          color: "var(--text-pri)",
                          lineHeight: 1.2,
                          marginBottom: 6,
                        }}
                      >
                        {featured.title}
                      </h2>
                    </Link>
                    <div
                      style={{
                        fontSize: "0.85rem",
                        color: "var(--text-sec)",
                        fontWeight: 600,
                        marginBottom: 6,
                      }}
                    >
                      {featured.artist}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        flexWrap: "wrap",
                      }}
                    >
                      <span style={{ fontSize: "0.72rem", color: "var(--text-mute)" }}>
                        {formatDateJa(featured.releaseDate)}
                      </span>
                      {yearsAgo(featured.releaseDate) > 0 && (
                        <span
                          style={{
                            fontSize: "0.72rem",
                            color: "var(--gold)",
                            background: "#c8a84b22",
                            border: "1px solid #c8a84b44",
                            padding: "1px 8px",
                            borderRadius: 3,
                            fontWeight: 700,
                          }}
                        >
                          {yearsAgo(featured.releaseDate)}年前
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {featured.note && (
                  <p
                    style={{
                      fontSize: "0.84rem",
                      color: "var(--text-pri)",
                      lineHeight: 1.8,
                      opacity: 0.88,
                      marginBottom: 16,
                    }}
                  >
                    {featured.note}
                  </p>
                )}

                <SvcGrid
                  links={featured.links}
                  trackTitle={featured.title}
                  artist={featured.artist}
                />

                <Link
                  href={`/track/${featured.id}`}
                  style={{
                    display: "inline-block",
                    marginTop: 12,
                    background: "none",
                    border: "1px solid var(--border)",
                    color: "var(--text-mute)",
                    borderRadius: 4,
                    padding: "6px 14px",
                    fontSize: "0.74rem",
                    fontFamily: "var(--font-body)",
                    textDecoration: "none",
                  }}
                >
                  詳細を見る →
                </Link>
              </div>
            )}

            {/* その他の楽曲一覧 */}
            {others.length > 0 && (
              <div style={{ paddingTop: 24 }}>
                <div
                  style={{
                    fontSize: "0.92rem",
                    fontWeight: 700,
                    color: "var(--text-pri)",
                    marginBottom: 4,
                  }}
                >
                  {month}月{day}日にリリースされた他の楽曲
                </div>
                <div
                  style={{
                    fontSize: "0.68rem",
                    color: "var(--text-mute)",
                    marginBottom: 16,
                    letterSpacing: "0.04em",
                  }}
                >
                  {others.length} TRACKS
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {others.map((track, i, arr) => {
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
                              padding: "14px 0 8px",
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
                            <div
                              style={{
                                flex: 1,
                                height: 1,
                                background: "var(--border)",
                              }}
                            />
                            <span style={{ fontSize: "0.66rem", color: "var(--gold)" }}>
                              {currentYear - parseInt(year)}年前
                            </span>
                          </div>
                        )}
                        <TrackCard track={track} index={i} />
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        ) : (
          <div style={{ textAlign: "center", padding: "72px 20px" }}>
            <div style={{ fontSize: "2rem", marginBottom: 12, color: "var(--text-mute)" }}>♪</div>
            <div style={{ fontSize: "0.86rem", color: "var(--text-sec)", marginBottom: 6 }}>
              この日のデータはまだありません
            </div>
            <div style={{ fontSize: "0.73rem", color: "var(--text-mute)" }}>
              前日・翌日ボタンで他の日付をご覧ください
            </div>
          </div>
        )}

        <div
          style={{
            marginTop: 48,
            paddingTop: 24,
            borderTop: "1px solid var(--border)",
            fontSize: "0.7rem",
            color: "var(--text-mute)",
            lineHeight: 1.9,
          }}
        >
          <span style={{ color: "var(--gold)", fontWeight: 700 }}>Release Tune</span>
          　その日にリリースされた楽曲を年代を超えてご紹介します。
        </div>
      </div>
    </>
  );
}

// ── トラックカード ────────────────────────────────────────────

function TrackCard({ track, index }: { track: Track; index: number }) {
  const [hov, setHov] = useState(false);

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? "var(--surface2)" : "var(--surface1)",
        borderRadius: 8,
        padding: 14,
        display: "grid",
        gridTemplateColumns: "68px 1fr",
        gap: 14,
        animation: `fadeUp 0.35s ease both`,
        animationDelay: `${index * 70}ms`,
        transition: "background 0.15s",
      }}
    >
      <Link href={`/track/${track.id}`}>
        <Jacket jacket={track.jacket} title={track.title} size={68} />
      </Link>
      <div style={{ minWidth: 0 }}>
        <Link
          href={`/track/${track.id}`}
          style={{ textDecoration: "none" }}
          onClick={() =>
            gaEvent("view_track", {
              track_id: track.id,
              track_title: track.title,
              artist: track.artist,
            })
          }
        >
          <div
            style={{
              fontSize: "0.95rem",
              fontWeight: 700,
              color: "var(--text-pri)",
              lineHeight: 1.3,
              marginBottom: 2,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {track.title}
          </div>
        </Link>
        <div
          style={{
            fontSize: "0.8rem",
            color: "var(--text-sec)",
            marginBottom: 8,
            fontWeight: 500,
          }}
        >
          {track.artist}
        </div>
        {track.note && (
          <div
            style={{
              fontSize: "0.74rem",
              color: "var(--text-pri)",
              lineHeight: 1.7,
              marginBottom: 10,
              opacity: 0.85,
            }}
          >
            {track.note}
          </div>
        )}
        <TrackSvcLinks
          links={track.links}
          trackTitle={track.title}
          artist={track.artist}
        />
      </div>
    </div>
  );
}

// ── NavBtn ────────────────────────────────────────────────────

function NavBtn({
  onClick,
  children,
  accent,
}: {
  onClick: () => void;
  children: React.ReactNode;
  accent?: boolean;
}) {
  const [hov, setHov] = useState(false);

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? "var(--surface2)" : "var(--surface1)",
        border: `1px solid ${accent ? "#c8a84b66" : "var(--border)"}`,
        color: accent ? "var(--gold)" : "var(--text-sec)",
        borderRadius: 4,
        padding: "6px 14px",
        fontSize: "0.76rem",
        cursor: "pointer",
        whiteSpace: "nowrap",
        fontFamily: "inherit",
        transition: "background 0.15s",
        fontWeight: accent ? 600 : 400,
      }}
    >
      {children}
    </button>
  );
}
