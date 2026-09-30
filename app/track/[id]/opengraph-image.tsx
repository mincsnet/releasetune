import { ImageResponse } from "next/og";
import { getTrackById, yearsAgo, formatDateJa } from "@/lib/tracks";
import { socialTitle } from "@/lib/utils";

// X・Threads などでリンクをシェアしたときのカード画像。
// X のカードは画像とドメインしか表示しないので、画像だけで日付・曲名・年数が伝わるようにする

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "楽曲のリリース情報";

const GOLD = "#c8a84b";
const TAGLINE = "今日はあの曲のリリース日";
const JACKET = 502;

// Google Fonts から、画像に使う文字だけを含むフォントを取得する（日本語フォント全体は数MBあるため）
async function loadFonts(family: string, weights: number[], text: string) {
  const url = `https://fonts.googleapis.com/css2?family=${family.replace(/ /g, "+")}:wght@${weights.join(";")}&text=${encodeURIComponent(text)}`;
  const css = await (await fetch(url)).text();
  const faces = [...css.matchAll(/font-weight: (\d+);\s*src: url\((.+?)\) format\('(?:truetype|opentype)'\)/g)];
  if (faces.length !== weights.length) throw new Error(`フォントを取得できません: ${family}`);
  return Promise.all(
    faces.map(async ([, weight, src]) => ({
      name: family,
      data: await (await fetch(src)).arrayBuffer(),
      weight: Number(weight) as 500 | 700,
      style: "normal" as const,
    }))
  );
}

// ジャケットは先に取得しておき、取得できなければ♪の代替表示にする（画像生成全体を失敗させない）
async function loadJacket(url?: string): Promise<string | null> {
  if (!url) return null;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const type = res.headers.get("content-type") ?? "image/jpeg";
    return `data:${type};base64,${Buffer.from(await res.arrayBuffer()).toString("base64")}`;
  } catch {
    return null;
  }
}

// 曲名の長さに応じて文字サイズと最大行数を決める（全角1文字=1、半角=0.55で数える）。
// アーティスト名が2行になっても右下のロゴに届かない高さに収める
function titleStyle(title: string): { fontSize: number; lines: number } {
  const width = [...title].reduce((w, c) => w + (c.charCodeAt(0) < 0x2000 ? 0.55 : 1), 0);
  if (width <= 7) return { fontSize: 72, lines: 2 };
  if (width <= 14) return { fontSize: 64, lines: 2 };
  if (width <= 18) return { fontSize: 52, lines: 2 };
  return { fontSize: 44, lines: 3 };
}

export default async function Image({ params }: { params: { id: string } }) {
  const result = await getTrackById(params.id);
  if (!result) return new Response("Not found", { status: 404 });

  const { track } = result;
  const title = socialTitle(track.title);
  const years = yearsAgo(track.releaseDate);
  const date = `${formatDateJa(track.releaseDate)}リリース`;
  // 今年のリリースは年数を出さない（サイトの表示と同じ）
  const badge = years > 0 ? `${years}年前` : "";
  const titleSize = titleStyle(title);

  const [sans, logo, jacket] = await Promise.all([
    loadFonts("Noto Sans JP", [500, 700], title + track.artist + date + badge + TAGLINE + "♪…"),
    loadFonts("Zen Old Mincho", [700], "ReleaseTun"),
    loadJacket(track.jacket),
  ]);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          gap: 60,
          padding: 64,
          background: "#0f0f0f",
          fontFamily: "Noto Sans JP",
        }}
      >
        {jacket ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={jacket} width={JACKET} height={JACKET} style={{ borderRadius: 8, objectFit: "cover" }} alt="" />
        ) : (
          <div
            style={{
              width: JACKET,
              height: JACKET,
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 8,
              background: "linear-gradient(135deg, #c8a84b33 0%, #1e1e1e 100%)",
              color: "#c8a84bcc",
              fontSize: 160,
            }}
          >
            ♪
          </div>
        )}

        <div
          style={{
            flex: 1,
            height: JACKET,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            minWidth: 0,
          }}
        >
          {/* 想定より長くなってもロゴに重ならないよう、はみ出した分は切る */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", minHeight: 0, flexShrink: 1, overflow: "hidden" }}>
            <div style={{ fontSize: 30, fontWeight: 500, color: GOLD }}>{date}</div>
            <div
              style={{
                display: "block",
                lineClamp: titleSize.lines,
                marginTop: 16,
                fontSize: titleSize.fontSize,
                fontWeight: 700,
                lineHeight: 1.25,
                color: "#ffffff",
              }}
            >
              {title}
            </div>
            <div
              style={{
                display: "block",
                lineClamp: 2,
                marginTop: 16,
                fontSize: 32,
                fontWeight: 500,
                lineHeight: 1.35,
                color: "#b3b3b3",
              }}
            >
              {track.artist}
            </div>
            {badge && (
              <div
                style={{
                  marginTop: 24,
                  padding: "4px 22px",
                  borderRadius: 999,
                  background: GOLD,
                  color: "#0f0f0f",
                  fontSize: 30,
                  fontWeight: 700,
                }}
              >
                {badge}
              </div>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6, flexShrink: 0 }}>
            <div style={{ display: "flex", gap: 12, fontFamily: "Zen Old Mincho", fontSize: 36, letterSpacing: 3.6 }}>
              <span style={{ color: GOLD }}>Release</span>
              <span style={{ color: "#b3b3b3" }}>Tune</span>
            </div>
            <div style={{ fontSize: 20, fontWeight: 500, color: "#6a6a6a" }}>{TAGLINE}</div>
          </div>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [...sans, ...logo],
      // next/og の既定は「1年間変わらない画像」扱い（immutable）。それだと「◯年前」や曲名の修正が画像に反映されないので、
      // CDN では1日で作り直す（X・Threads は取得した画像をそれぞれ独自にキャッシュする）。既定と同じ小文字のキーで上書きする
      headers: { "cache-control": "public, max-age=86400, s-maxage=86400, stale-while-revalidate=86400" },
    }
  );
}
