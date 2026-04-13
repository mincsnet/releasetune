"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import type { Track } from "@/lib/utils";
import { formatDateJa, yearsAgo } from "@/lib/utils";
import { Jacket } from "@/components/Jacket";
import { TrackSvcLinks } from "@/components/SvcLinks";
import { gaEvent } from "@/components/GoogleAnalytics";

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
    <div style={{ maxWidth: 600, margin: "0 auto", padding: "24px 20px 60px" }}>

      {/* 検索フォーム */}
      <form onSubmit={handleSubmit} style={{ marginBottom: 28 }}>
        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "center",
            background: "var(--surface1)",
            border: "1px solid #c8a84b44",
            borderRadius: 10,
            padding: "4px 4px 4px 16px",
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-mute)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="楽曲タイトル・アーティスト名で検索..."
            autoFocus
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--text-pri)",
              fontSize: "0.95rem",
              fontFamily: "inherit",
              padding: "8px 0",
            }}
          />
          <button
            type="submit"
            disabled={isPending || !input.trim()}
            style={{
              background: input.trim() ? "#c8a84b" : "var(--surface2)",
              border: "none",
              borderRadius: 7,
              color: input.trim() ? "#000" : "var(--text-mute)",
              padding: "8px 16px",
              fontSize: "0.82rem",
              fontWeight: 700,
              cursor: input.trim() ? "pointer" : "default",
              fontFamily: "inherit",
              transition: "background 0.15s",
              whiteSpace: "nowrap",
            }}
          >
            {isPending ? "検索中..." : "検索"}
          </button>
        </div>
      </form>

      {/* 結果表示 */}
      {query && (
        <>
          <div
            style={{
              fontSize: "0.78rem",
              color: "var(--text-mute)",
              marginBottom: 16,
            }}
          >
            {results.length > 0 ? (
              <>
                「<span style={{ color: "var(--gold)" }}>{query}</span>」の検索結果：
                <span style={{ marginLeft: 6, color: "var(--text-sec)" }}>{results.length} 件</span>
                {results.length >= 50 && (
                  <span style={{ marginLeft: 6, color: "var(--text-mute)" }}>（上位50件を表示）</span>
                )}
              </>
            ) : (
              <>
                「<span style={{ color: "var(--gold)" }}>{query}</span>」に一致する楽曲が見つかりませんでした
              </>
            )}
          </div>

          {results.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {results.map((track, i) => (
                <SearchResultCard key={track.id} track={track} index={i} />
              ))}
            </div>
          )}

          {results.length === 0 && (
            <div style={{ textAlign: "center", padding: "48px 20px", color: "var(--text-mute)" }}>
              <div style={{ fontSize: "2rem", marginBottom: 12 }}>♪</div>
              <div style={{ fontSize: "0.86rem", marginBottom: 8 }}>
                別のキーワードで試してみてください
              </div>
              <div style={{ fontSize: "0.74rem" }}>
                例：アーティスト名、楽曲タイトルの一部
              </div>
            </div>
          )}
        </>
      )}

      {/* 初期状態 */}
      {!query && (
        <div style={{ textAlign: "center", padding: "48px 20px", color: "var(--text-mute)" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: 16 }}>🎵</div>
          <div style={{ fontSize: "0.88rem", color: "var(--text-sec)", marginBottom: 8 }}>
            楽曲タイトルやアーティスト名を入力してください
          </div>
          <div style={{ fontSize: "0.74rem" }}>
            32,000曲以上のデータから検索できます
          </div>
        </div>
      )}
    </div>
  );
}

// ── 検索結果カード ────────────────────────────────────────────

function SearchResultCard({ track, index }: { track: SearchResult; index: number }) {
  const [hov, setHov] = useState(false);
  const years = yearsAgo(track.releaseDate);
  const [m, d] = track.mmdd.split("-").map(Number);

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
        animationDelay: `${Math.min(index * 30, 400)}ms`,
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
        <Link
          href={`/artist/${encodeURIComponent(track.artist)}`}
          style={{ textDecoration: "none" }}
        >
          <div style={{ fontSize: "0.8rem", color: "var(--text-sec)", marginBottom: 4, fontWeight: 500 }}>
            {track.artist}
          </div>
        </Link>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.72rem", color: "var(--text-mute)" }}>
            {formatDateJa(track.releaseDate)}
          </span>
          {years > 0 && (
            <span
              style={{
                fontSize: "0.68rem",
                color: "var(--gold)",
                background: "#c8a84b22",
                border: "1px solid #c8a84b44",
                padding: "1px 7px",
                borderRadius: 3,
                fontWeight: 700,
              }}
            >
              {years}年前
            </span>
          )}
          <Link
            href={`/date/${track.mmdd}`}
            style={{ textDecoration: "none" }}
          >
            <span style={{ fontSize: "0.68rem", color: "var(--text-mute)" }}>
              {m}月{d}日のリリース →
            </span>
          </Link>
        </div>
        <TrackSvcLinks links={track.links} trackTitle={track.title} artist={track.artist} />
      </div>
    </div>
  );
}
