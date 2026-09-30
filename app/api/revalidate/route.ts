import { NextResponse } from "next/server";
import { revalidateTag } from "next/cache";
import { TRACKS_CACHE_TAG } from "@/lib/tracks";

// Supabase の tracks を書き換えた直後（紹介文の公開など）に呼び、データ取得のキャッシュを消す。
// 呼ばないと、日付ページは最大1時間・楽曲詳細は最大24時間、古い内容のまま表示される。
// 呼び出し元: scripts/notes の同期スクリプト（sync_review.py）とローカルのレビュー画面（review_server.py）
export const runtime = "nodejs";

export async function POST(request: Request) {
  const authHeader = request.headers.get("authorization");
  if (!process.env.CRON_SECRET || authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  revalidateTag(TRACKS_CACHE_TAG);
  return NextResponse.json({ revalidated: TRACKS_CACHE_TAG, at: new Date().toISOString() });
}
