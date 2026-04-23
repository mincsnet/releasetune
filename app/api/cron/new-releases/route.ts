import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

// Vercel Cron Job から呼ばれる
// vercel.json で毎日 JST 0:00（UTC 15:00）に実行
export const runtime = "nodejs";
export const maxDuration = 60;

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

interface ItunesEntry {
  "im:artist": { label: string };
  "im:name":   { label: string };
  "im:releaseDate": { label: string };
  "im:image": { label: string; attributes: { height: string } }[];
  id: { attributes: { "im:id": string } };
  link: { attributes: { href: string } };
}

function mmdd(dateStr: string): string {
  return dateStr.slice(5, 10); // "YYYY-MM-DD" → "MM-DD"
}

export async function GET(request: Request) {
  // Vercel Cron の認証チェック
  const authHeader = request.headers.get("authorization");
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    // iTunes RSS Feed から新着100件取得
    const resp = await fetch(
      "https://itunes.apple.com/jp/rss/topalbums/limit=100/json",
      { next: { revalidate: 0 } }
    );
    if (!resp.ok) throw new Error(`iTunes RSS fetch failed: ${resp.status}`);

    const data = await resp.json();
    const entries: ItunesEntry[] = data?.feed?.entry ?? [];

    if (!entries.length) {
      return NextResponse.json({ message: "No entries found", added: 0 });
    }

    // Supabaseにupsertするレコードを構築
    const rows = entries.map((e) => {
      const releaseDate = e["im:releaseDate"].label.slice(0, 10);
      const jacket = e["im:image"]
        .sort((a, b) => Number(b.attributes.height) - Number(a.attributes.height))[0]
        ?.label.replace("100x100bb", "600x600bb") ?? "";
      const trackId = e.id.attributes["im:id"];

      return {
        id:           trackId,
        title:        e["im:name"].label,
        artist:       e["im:artist"].label,
        release_date: releaseDate,
        mmdd:         mmdd(releaseDate),
        jacket,
        apple:        e.link.attributes.href,
        spotify:      null,
        amazon:       null,
        youtube:      null,
        youtube_id:   null,
        youtube_verified: false,
        note:         null,
        note_verified: false,
      };
    });

    // upsert（既存IDは更新しない = on_conflict: id → do nothing）
    const { error, count } = await supabase
      .from("tracks")
      .upsert(rows, { onConflict: "id", ignoreDuplicates: true })
      .select("id");

    if (error) throw new Error(error.message);

    return NextResponse.json({
      message: "New releases fetched",
      fetched: entries.length,
      added:   count ?? 0,
      sample:  rows.slice(0, 3).map((r) => `${r.artist} | ${r.title}`),
    });

  } catch (err) {
    console.error("[cron/new-releases]", err);
    return NextResponse.json(
      { error: String(err) },
      { status: 500 }
    );
  }
}
