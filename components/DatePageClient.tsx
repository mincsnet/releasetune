"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import type { Track } from "@/lib/utils";
import type { DebutInfo } from "@/lib/tracks";
import { yearsAgo, formatDateJa, parseMmdd } from "@/lib/utils";
import { Jacket } from "@/components/Jacket";
import { SvcGrid, TrackSvcLinks } from "@/components/SvcLinks";
import { gaEvent } from "@/components/GoogleAnalytics";

interface DebutWithTrack extends DebutInfo {
  track?: Track;
}

interface Props {
  mmdd: string;
  tracks: Track[];
  today: string;
  debuts?: DebutWithTrack[];
}

export function DatePageClient({ mmdd, tracks, today, debuts = [] }: Props) {
  const router = useRouter();
  const { month, day } = parseMmdd(mmdd);
  const isToday = mmdd === today;
  const [calOpen, setCalOpen] = useState(false);
  const [calYear, setCalYear] = useState(() => {
    const [m] = mmdd.split("-").map(Number);
    return m <= 2 ? 2025 : 2026; // 表示年の初期値（適当に現在年）
  });
  const [calMonth, setCalMonth] = useState(() => parseInt(mmdd.split("-")[0]));

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

  // 前日・翌日の月日を計算
  const prevDate = (() => {
    const [m, d] = mmdd.split("-").map(Number);
    const b = new Date(2024, m - 1, d - 1);
    return { month: b.getMonth() + 1, day: b.getDate() };
  })();
  const nextDate = (() => {
    const [m, d] = mmdd.split("-").map(Number);
    const b = new Date(2024, m - 1, d + 1);
    return { month: b.getMonth() + 1, day: b.getDate() };
  })();

  return (
    <>
      {/* ナビゲーション */}
      <div
        style={{
          maxWidth: 600,
          margin: "0 auto",
          padding: "12px 20px 0",
          borderBottom: calOpen ? "none" : "1px solid var(--border)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
          {/* 前日ボタン */}
          <NavBtn onClick={() => shiftDate(-1)}>
            <span style={{ fontSize: "0.6rem", opacity: 0.5 }}>◀</span>
            {" "}{prevDate.month}月{prevDate.day}日
          </NavBtn>

          {/* 当日枠：タップでカレンダー開閉 */}
          <button
            onClick={() => setCalOpen((v) => !v)}
            style={{
              background: "var(--surface1)",
              border: "1px solid #c8a84b44",
              borderRadius: 6,
              padding: "5px 16px",
              textAlign: "center",
              minWidth: 110,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            <div style={{ fontSize: "0.58rem", color: "var(--text-mute)", letterSpacing: "0.14em", marginBottom: 2 }}>
              ON THIS DAY
            </div>
            <div style={{ fontFamily: "var(--font-display)", fontSize: "1.1rem", fontWeight: 700, color: "var(--text-pri)", lineHeight: 1, marginBottom: 2 }}>
              {month}月{day}日
            </div>
            <div style={{ fontSize: "0.58rem", color: "var(--text-mute)" }}>
              {calOpen ? "▲ 閉じる" : "タップで日付選択"}
            </div>
          </button>

          {/* 翌日ボタン */}
          <NavBtn onClick={() => shiftDate(1)}>
            {nextDate.month}月{nextDate.day}日{" "}
            <span style={{ fontSize: "0.6rem", opacity: 0.5 }}>▶</span>
          </NavBtn>
        </div>

        {/* 今日に戻るボタン */}
        {!isToday && (
          <div style={{ textAlign: "center", marginTop: 8, paddingBottom: calOpen ? 0 : 12 }}>
            <NavBtn onClick={() => router.push("/")} accent>今日に戻る</NavBtn>
          </div>
        )}

        {/* カレンダー */}
        {calOpen && (
          <CalendarPicker
            mmdd={mmdd}
            calYear={calYear}
            calMonth={calMonth}
            setCalYear={setCalYear}
            setCalMonth={setCalMonth}
            onSelect={(m, d) => {
              const next = `${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
              setCalOpen(false);
              gaEvent("navigate_date", { date: next });
              router.push(`/date/${next}`);
            }}
          />
        )}
      </div>

      {/* デビュー記念日バナー */}
      {debuts.length > 0 && (
        <div style={{ maxWidth: 600, margin: "0 auto", padding: "0 20px" }}>
          {debuts.map((d) => (
            <Link
              key={d.artist}
              href={`/artist/${encodeURIComponent(d.artist)}`}
              style={{ textDecoration: "none", display: "block", marginBottom: 8 }}
            >
              <div
                style={{
                  background: "#c8a84b18",
                  border: "1px solid #c8a84b44",
                  borderRadius: 8,
                  padding: "10px 16px",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                }}
              >
                <span style={{ fontSize: "1rem" }}>🎂</span>
                <div style={{ minWidth: 0 }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--gold)", fontWeight: 700 }}>
                    {d.artist}
                  </span>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-sec)" }}>
                    {" "}のデビュー記念日
                  </span>
                  {d.debutTrack && (
                    <span style={{ fontSize: "0.72rem", color: "var(--text-mute)", marginLeft: 6 }}>
                      「{d.debutTrack}」
                    </span>
                  )}
                  <span style={{ fontSize: "0.72rem", color: "var(--text-mute)", marginLeft: 4 }}>
                    {new Date().getFullYear() - parseInt(d.debutDate.slice(0, 4))}周年
                  </span>
                </div>
                <span style={{ marginLeft: "auto", color: "var(--text-mute)", fontSize: "0.8rem", flexShrink: 0 }}>›</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* コンテンツ */}
      <div style={{ maxWidth: 600, margin: "0 auto", padding: "0 20px 60px" }}>
        {tracks.length > 0 ? (
          <>
            {/* フィーチャード楽曲 */}
            {featured && (
              <div style={{ padding: "28px 0", borderBottom: "1px solid var(--border)" }}>
                {/* ジャケット：約2/3幅・中央寄せ */}
                <Link
                  href={`/track/${featured.id}`}
                  style={{
                    display: "block",
                    width: "66%",
                    margin: "0 auto 20px",
                    borderRadius: 12,
                    overflow: "hidden",
                  }}
                  onClick={() => gaEvent("view_track", { track_id: featured.id, track_title: featured.title, artist: featured.artist })}
                >
                  <Jacket jacket={featured.jacket} title={featured.title} fullWidth />
                </Link>

                {/* タイトル・アーティスト・リリース日：中央寄せ */}
                <div style={{ textAlign: "center", marginBottom: 20 }}>
                  <Link href={`/track/${featured.id}`} style={{ textDecoration: "none" }}>
                    <h2
                      style={{
                        fontFamily: "var(--font-display)",
                        fontSize: "clamp(1.2rem, 5vw, 1.8rem)",
                        fontWeight: 700,
                        color: "var(--text-pri)",
                        lineHeight: 1.25,
                        marginBottom: 10,
                      }}
                    >
                      {featured.title}
                    </h2>
                  </Link>
                  <div style={{ fontSize: "0.95rem", color: "var(--text-sec)", fontWeight: 600, marginBottom: 8 }}>
                    {featured.artist}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, flexWrap: "wrap" }}>
                    <span style={{ fontSize: "0.76rem", color: "var(--text-mute)" }}>
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

                {/* コメント */}
                {featured.note && (
                  <p style={{ fontSize: "0.84rem", color: "var(--text-pri)", lineHeight: 1.8, opacity: 0.88, marginBottom: 20 }}>
                    {featured.note}
                  </p>
                )}

                {/* 試聴リンク */}
                <SvcGrid links={featured.links} trackTitle={featured.title} artist={featured.artist} />

                {/* YouTube埋め込み */}
                {featured.links?.youtubeId && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: "0.64rem", color: "var(--text-mute)", letterSpacing: "0.1em", marginBottom: 8 }}>
                      MV / 公式動画
                    </div>
                    <div style={{ borderRadius: 10, overflow: "hidden", aspectRatio: "16/9", background: "#000" }}>
                      <iframe
                        src={`https://www.youtube.com/embed/${featured.links.youtubeId}?rel=0`}
                        title={`${featured.title} - ${featured.artist}`}
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                        style={{ width: "100%", height: "100%", border: "none", display: "block" }}
                      />
                    </div>
                  </div>
                )}

                <Link
                  href={`/track/${featured.id}`}
                  style={{
                    display: "inline-block",
                    marginTop: 14,
                    border: "1px solid var(--border)",
                    color: "var(--text-mute)",
                    borderRadius: 4,
                    padding: "6px 14px",
                    fontSize: "0.74rem",
                    textDecoration: "none",
                  }}
                >
                  詳細を見る →
                </Link>
              </div>
            )}

            {/* その他の楽曲一覧（旧来の横並びレイアウト） */}
            {others.length > 0 && (
              <div style={{ paddingTop: 24 }}>
                <div style={{ fontSize: "0.92rem", fontWeight: 700, color: "var(--text-pri)", marginBottom: 4 }}>
                  {month}月{day}日にリリースされた他の楽曲
                </div>
                <div style={{ fontSize: "0.68rem", color: "var(--text-mute)", marginBottom: 16, letterSpacing: "0.04em" }}>
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
                          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 0 8px" }}>
                            <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-mute)", letterSpacing: "0.1em" }}>
                              {year}
                            </span>
                            <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
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

        <div style={{ marginTop: 48, paddingTop: 24, borderTop: "1px solid var(--border)", fontSize: "0.7rem", color: "var(--text-mute)", lineHeight: 1.9 }}>
          <span style={{ color: "var(--gold)", fontWeight: 700 }}>Release Tune</span>
          　その日にリリースされた楽曲を年代を超えてご紹介します。
        </div>
      </div>
    </>
  );
}

// ── トラックカード（横並びレイアウト） ────────────────────────────

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
          style={{ fontSize: "0.8rem", color: "var(--text-sec)", marginBottom: 8, fontWeight: 500, display: "block", textDecoration: "none" }}
        >
          {track.artist}
        </Link>
        {track.note && (
          <div style={{ fontSize: "0.74rem", color: "var(--text-pri)", lineHeight: 1.7, marginBottom: 10, opacity: 0.85 }}>
            {track.note}
          </div>
        )}
        <TrackSvcLinks links={track.links} trackTitle={track.title} artist={track.artist} />
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

// ── カレンダーピッカー ────────────────────────────────────────

const MONTHS_JA = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];
const DOWS_JA = ["日","月","火","水","木","金","土"];

function CalendarPicker({
  mmdd,
  calYear,
  calMonth,
  setCalYear,
  setCalMonth,
  onSelect,
}: {
  mmdd: string;
  calYear: number;
  calMonth: number;
  setCalYear: (y: number) => void;
  setCalMonth: (m: number) => void;
  onSelect: (month: number, day: number) => void;
}) {
  const [curM, curD] = mmdd.split("-").map(Number);

  function prevMonth() {
    if (calMonth === 1) { setCalYear(calYear - 1); setCalMonth(12); }
    else setCalMonth(calMonth - 1);
  }
  function nextMonth() {
    if (calMonth === 12) { setCalYear(calYear + 1); setCalMonth(1); }
    else setCalMonth(calMonth + 1);
  }

  // その月の1日の曜日と日数
  const firstDow = new Date(calYear, calMonth - 1, 1).getDay();
  const daysInMonth = new Date(calYear, calMonth, 0).getDate();

  // 今日
  const todayStr = new Date().toLocaleDateString("sv-SE"); // YYYY-MM-DD
  const todayMonth = parseInt(todayStr.slice(5, 7));
  const todayDay = parseInt(todayStr.slice(8, 10));

  return (
    <div
      style={{
        borderBottom: "1px solid var(--border)",
        padding: "10px 0 14px",
      }}
    >
      {/* 月ヘッダー */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <button
          onClick={prevMonth}
          style={{ background: "transparent", border: "1px solid var(--border)", color: "var(--text-mute)", borderRadius: 4, padding: "3px 10px", fontSize: "0.76rem", cursor: "pointer", fontFamily: "inherit" }}
        >
          ◀
        </button>
        <span style={{ fontFamily: "var(--font-display)", fontSize: "0.95rem", color: "var(--text-pri)", fontWeight: 700 }}>
          {MONTHS_JA[calMonth - 1]}
        </span>
        <button
          onClick={nextMonth}
          style={{ background: "transparent", border: "1px solid var(--border)", color: "var(--text-mute)", borderRadius: 4, padding: "3px 10px", fontSize: "0.76rem", cursor: "pointer", fontFamily: "inherit" }}
        >
          ▶
        </button>
      </div>

      {/* 曜日ヘッダー */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", marginBottom: 4 }}>
        {DOWS_JA.map((d, i) => (
          <div key={d} style={{ textAlign: "center", fontSize: "0.68rem", color: i === 0 ? "#c84b4b88" : i === 6 ? "#4b6ac888" : "var(--text-mute)", padding: "2px 0" }}>
            {d}
          </div>
        ))}
      </div>

      {/* 日付グリッド */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2 }}>
        {/* 空白セル */}
        {Array.from({ length: firstDow }).map((_, i) => (
          <div key={`empty-${i}`} />
        ))}
        {/* 日付セル */}
        {Array.from({ length: daysInMonth }).map((_, i) => {
          const d = i + 1;
          const isSelected = calMonth === curM && d === curD;
          const isToday = calMonth === todayMonth && d === todayDay;
          const dow = (firstDow + i) % 7;
          return (
            <button
              key={d}
              onClick={() => onSelect(calMonth, d)}
              style={{
                background: isSelected ? "#c8a84b" : "transparent",
                color: isSelected ? "#000" : isToday ? "var(--gold)" : dow === 0 ? "#c84b4b99" : dow === 6 ? "#4b6ac899" : "var(--text-sec)",
                border: isToday && !isSelected ? "1px solid #c8a84b44" : "1px solid transparent",
                borderRadius: "50%",
                width: "100%",
                aspectRatio: "1/1",
                fontSize: "0.8rem",
                fontWeight: isSelected || isToday ? 700 : 400,
                cursor: "pointer",
                fontFamily: "inherit",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {d}
            </button>
          );
        })}
      </div>
    </div>
  );
}
