import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { getSpotifyToken, searchSpotify } from "@/lib/spotify";

// Vercel Cron から毎日呼ばれ、Spotify直リンクが未取得の既存曲を少しずつ埋める。
// Spotify Web APIはアプリ単位で1日あたり数百リクエスト程度しか使えない
// （2026-08-17〜18に実測: 約200〜260リクエストでQUOTA_EXCEEDEDになり、
//  Retry-Afterから逆算すると直近の初回呼び出しから約24時間のローリングウィンドウ）。
// そのため1回の実行で処理する件数を抑え、429を検出したら即座に打ち切る。
export const runtime = "nodejs";
export const maxDuration = 60;

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const BATCH_SIZE = 120; // 1回の実行で処理する上限（安全マージン込み）
const SLEEP_MS = 120; // Spotify検索リクエスト間のスリープ

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function GET(request: Request) {
  const authHeader = request.headers.get("authorization");
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const token = await getSpotifyToken();
  if (!token) {
    return NextResponse.json({ error: "Spotify token unavailable" }, { status: 500 });
  }

  const { searchParams } = new URL(request.url);
  const limitParam = Number(searchParams.get("limit"));
  const batchSize = Number.isFinite(limitParam) && limitParam > 0 ? Math.min(limitParam, BATCH_SIZE) : BATCH_SIZE;

  const { data: pending, error } = await supabase
    .from("tracks")
    .select("id,title,artist")
    .or("spotify.is.null,spotify.not.like.*open.spotify.com/track/*")
    .order("id", { ascending: true })
    .limit(batchSize);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  let processed = 0;
  let updated = 0;
  let notFound = 0;
  let quotaExceededRetryAfter: number | null = null;

  for (const track of pending ?? []) {
    const result = await searchSpotify(token, track.title, track.artist);

    if (result.quotaExceededRetryAfter !== undefined) {
      quotaExceededRetryAfter = result.quotaExceededRetryAfter;
      break;
    }

    processed++;

    if (result.url) {
      const { error: updateError } = await supabase
        .from("tracks")
        .update({ spotify: result.url })
        .eq("id", track.id);
      if (!updateError) updated++;
    } else {
      notFound++;
    }

    await sleep(SLEEP_MS);
  }

  return NextResponse.json({
    message: quotaExceededRetryAfter !== null ? "Stopped: Spotify quota exceeded" : "Batch complete",
    fetched: (pending ?? []).length,
    processed,
    updated,
    notFound,
    quotaExceededRetryAfterSeconds: quotaExceededRetryAfter,
  });
}
