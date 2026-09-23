import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { getSpotifyToken, searchSpotify } from "@/lib/spotify";

// Vercel Cron から毎日呼ばれ、Spotify直リンクが未取得の既存曲を少しずつ埋める。
// Spotify Web APIはアプリ単位で1日あたり数百リクエスト程度しか使えない
// （2026-08-17〜18に実測: 約200〜260リクエストでQUOTA_EXCEEDEDになり、
//  Retry-Afterから逆算すると直近の初回呼び出しから約24時間のローリングウィンドウ）。
// そのため429を検出したら即座に打ち切る。
//
// 実測（2026-09-23）: 1トラックあたり平均約1.3秒（Spotify検索の実ネットワーク往復が支配的。
// 未ヒット時は最大3クエリ試行するためさらに長くなる）。固定件数を上限にすると
// Vercelのファンクションタイムアウト（maxDuration）に達して処理が強制打ち切りになり、
// 実際の処理件数がクォータ上限よりずっと少なくなっていたため、件数ではなく
// 経過時間で打ち切る方式にしている。
export const runtime = "nodejs";
export const maxDuration = 60;

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const FETCH_LIMIT = 200; // Supabaseから一度に取得する候補件数の上限
const TIME_BUDGET_MS = 45_000; // maxDuration(60s)に対して、レスポンス生成等の余裕を見て打ち切る経過時間
const SLEEP_MS = 80; // Spotify検索リクエスト間のスリープ

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
  const fetchLimit = Number.isFinite(limitParam) && limitParam > 0 ? Math.min(limitParam, FETCH_LIMIT) : FETCH_LIMIT;

  const { data: pending, error } = await supabase
    .from("tracks")
    .select("id,title,artist")
    .or("spotify.is.null,spotify.not.like.*open.spotify.com/track/*")
    .order("id", { ascending: true })
    .limit(fetchLimit);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const startedAt = Date.now();
  let processed = 0;
  let updated = 0;
  let notFound = 0;
  let quotaExceededRetryAfter: number | null = null;
  let timeBudgetExceeded = false;

  for (const track of pending ?? []) {
    if (Date.now() - startedAt > TIME_BUDGET_MS) {
      timeBudgetExceeded = true;
      break;
    }

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

  const message = quotaExceededRetryAfter !== null
    ? "Stopped: Spotify quota exceeded"
    : timeBudgetExceeded
    ? "Stopped: time budget reached (resumes from the same query next run)"
    : "Batch complete";

  return NextResponse.json({
    message,
    fetched: (pending ?? []).length,
    processed,
    updated,
    notFound,
    elapsedMs: Date.now() - startedAt,
    quotaExceededRetryAfterSeconds: quotaExceededRetryAfter,
  });
}
