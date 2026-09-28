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
import styles from "./DatePageClient.module.css";

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

  const featuredIdx = useMemo(() => {
    if (tracks.length === 0) return 0;
    // mmddから決定的に算出（サーバー/クライアントで結果を一致させるため乱数は使わない）
    let hash = 0;
    for (let i = 0; i < mmdd.length; i++) {
      hash = (hash * 31 + mmdd.charCodeAt(i)) | 0;
    }
    return Math.abs(hash) % tracks.length;
  }, [tracks.length, mmdd]);
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
      <div className={`${styles.nav} ${calOpen ? styles.navCalOpen : ""}`}>
        <div className={styles.navRow}>
          {/* 前日ボタン */}
          <NavBtn onClick={() => shiftDate(-1)}>
            <span className={styles.navArrow}>◀</span>
            {" "}{prevDate.month}月{prevDate.day}日
          </NavBtn>

          {/* 当日枠：タップでカレンダー開閉 */}
          <button onClick={() => setCalOpen((v) => !v)} className={styles.dateToggle}>
            <div className={styles.dateToggleEyebrow}>ON THIS DAY</div>
            <div className={styles.dateToggleDate}>
              {month}月{day}日
            </div>
            <div className={styles.dateToggleHint}>
              {calOpen ? "▲ 閉じる" : "タップで日付選択"}
            </div>
          </button>

          {/* 翌日ボタン */}
          <NavBtn onClick={() => shiftDate(1)}>
            {nextDate.month}月{nextDate.day}日{" "}
            <span className={styles.navArrow}>▶</span>
          </NavBtn>
        </div>

        {/* 今日に戻るボタン */}
        {!isToday && (
          <div className={`${styles.backToday} ${calOpen ? styles.backTodayCalOpen : ""}`}>
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
        <div className={styles.debuts}>
          {debuts.map((d) => (
            <Link
              key={d.artist}
              href={`/artist/${encodeURIComponent(d.artist)}`}
              className={styles.debutLink}
            >
              <div className={styles.debut}>
                <span className={styles.debutIcon}>🎂</span>
                <div className={styles.debutText}>
                  <span className={styles.debutArtist}>{d.artist}</span>
                  <span className={styles.debutLabel}>{" "}のデビュー記念日</span>
                  {d.debutTrack && (
                    <span className={styles.debutTrack}>「{d.debutTrack}」</span>
                  )}
                  <span className={styles.debutYears}>
                    {new Date().getFullYear() - parseInt(d.debutDate.slice(0, 4))}周年
                  </span>
                </div>
                <span className={styles.debutChevron}>›</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* コンテンツ */}
      <div className={styles.content}>
        {tracks.length > 0 ? (
          <>
            {/* フィーチャード楽曲 */}
            {featured && (
              <div className={styles.featured}>
                <Link
                  href={`/track/${featured.id}`}
                  className={styles.featuredJacket}
                  onClick={() => gaEvent("view_track", { track_id: featured.id, track_title: featured.title, artist: featured.artist })}
                >
                  <Jacket jacket={featured.jacket} title={featured.title} fullWidth />
                </Link>

                <div>
                  <div className={styles.featuredHead}>
                    <Link href={`/track/${featured.id}`} className={styles.plainLink}>
                      <h2 className={styles.featuredTitle}>{featured.title}</h2>
                    </Link>
                    <div className={styles.featuredArtist}>{featured.artist}</div>
                    <div className={styles.featuredMeta}>
                      <span className={styles.featuredDate}>{formatDateJa(featured.releaseDate)}</span>
                      {yearsAgo(featured.releaseDate) > 0 && (
                        <span className={styles.yearsBadge}>{yearsAgo(featured.releaseDate)}年前</span>
                      )}
                    </div>
                  </div>

                  {featured.note && <p className={styles.featuredNote}>{featured.note}</p>}

                  <SvcGrid links={featured.links} trackTitle={featured.title} artist={featured.artist} />

                  {featured.links?.youtubeId && featured.links?.youtubeVerified && (
                    <div className={styles.mv}>
                      <div className={styles.mvLabel}>MV / 公式動画</div>
                      <div className={styles.mvFrame}>
                        <iframe
                          src={`https://www.youtube.com/embed/${featured.links.youtubeId}?rel=0`}
                          title={`${featured.title} - ${featured.artist}`}
                          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                          allowFullScreen
                          className={styles.mvIframe}
                        />
                      </div>
                    </div>
                  )}

                  <Link href={`/track/${featured.id}`} className={styles.detailLink}>
                    詳細を見る →
                  </Link>
                </div>
              </div>
            )}

            {/* その他の楽曲一覧 */}
            {others.length > 0 && (
              <div className={styles.others}>
                <div className={styles.othersHeading}>
                  {month}月{day}日にリリースされた他の楽曲
                </div>
                <div className={styles.othersCount}>{others.length} TRACKS</div>
                <div className={styles.othersList}>
                  {others.map((track, i, arr) => {
                    const year = track.releaseDate.split("-")[0];
                    const prevYear = arr[i - 1]?.releaseDate.split("-")[0];
                    const currentYear = new Date().getFullYear();
                    return (
                      <div key={track.id} className={styles.othersItem}>
                        {year !== prevYear && (
                          <div className={styles.yearHeader}>
                            <span className={styles.yearLabel}>{year}</span>
                            <div className={styles.yearRule} />
                            <span className={styles.yearAgo}>{currentYear - parseInt(year)}年前</span>
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
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>♪</div>
            <div className={styles.emptyTitle}>この日のデータはまだありません</div>
            <div className={styles.emptyHint}>前日・翌日ボタンで他の日付をご覧ください</div>
          </div>
        )}

        <div className={styles.about}>
          <span className={styles.aboutBrand}>Release Tune</span>
          　その日にリリースされた楽曲を年代を超えてご紹介します。
        </div>
      </div>
    </>
  );
}

// ── トラックカード（横並びレイアウト） ────────────────────────────

function TrackCard({ track, index }: { track: Track; index: number }) {
  return (
    <div className={styles.card} style={{ animationDelay: `${index * 70}ms` }}>
      <Link href={`/track/${track.id}`}>
        <Jacket jacket={track.jacket} title={track.title} size={68} />
      </Link>
      <div className={styles.cardBody}>
        <Link
          href={`/track/${track.id}`}
          className={styles.plainLink}
          onClick={() => gaEvent("view_track", { track_id: track.id, track_title: track.title, artist: track.artist })}
        >
          <div className={styles.cardTitle}>{track.title}</div>
        </Link>
        <Link href={`/artist/${encodeURIComponent(track.artist)}`} className={styles.cardArtist}>
          {track.artist}
        </Link>
        {track.note && <div className={styles.cardNote}>{track.note}</div>}
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
  return (
    <button onClick={onClick} className={`${styles.navBtn} ${accent ? styles.navBtnAccent : ""}`}>
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
    <div className={styles.calendar}>
      {/* 月ヘッダー */}
      <div className={styles.calHeader}>
        <button onClick={prevMonth} className={styles.calMonthBtn}>◀</button>
        <span className={styles.calMonthLabel}>{MONTHS_JA[calMonth - 1]}</span>
        <button onClick={nextMonth} className={styles.calMonthBtn}>▶</button>
      </div>

      {/* 曜日ヘッダー */}
      <div className={styles.calDows}>
        {DOWS_JA.map((d, i) => (
          <div
            key={d}
            className={`${styles.calDow} ${i === 0 ? styles.calDowSun : i === 6 ? styles.calDowSat : ""}`}
          >
            {d}
          </div>
        ))}
      </div>

      {/* 日付グリッド */}
      <div className={styles.calDays}>
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
          const cls = [
            styles.calDay,
            dow === 0 && styles.calDaySun,
            dow === 6 && styles.calDaySat,
            isToday && styles.calDayToday,
            isSelected && styles.calDaySelected,
          ].filter(Boolean).join(" ");
          return (
            <button key={d} onClick={() => onSelect(calMonth, d)} className={cls}>
              {d}
            </button>
          );
        })}
      </div>
    </div>
  );
}
