import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { getSpotifyToken, searchSpotify } from "@/lib/spotify";

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

// ── YouTube 動画ID検索（fetch_youtube.py と同等のロジック） ──────

function isJapanese(text: string): boolean {
  return /[぀-ヿ一-鿿]/.test(text);
}

function cleanTitle(title: string): string {
  return title.replace(/\s*[-–]\s*(Single|EP|Album|Maxi Single|CD|DVD).*$/i, "").trim();
}

interface YoutubeSearchItem {
  id: { videoId: string };
  snippet: { channelTitle?: string; title?: string };
}

async function searchYoutube(
  title: string,
  artist: string
): Promise<{ id: string; verified: boolean } | null> {
  const apiKey = process.env.YOUTUBE_API_KEY;
  if (!apiKey) return null;

  const qTitle = cleanTitle(title);
  const hasJa = isJapanese(title) || isJapanese(artist);
  const query = hasJa ? `${artist} ${qTitle} 公式` : `${artist} ${qTitle} official`;

  try {
    const url = new URL("https://www.googleapis.com/youtube/v3/search");
    url.searchParams.set("part", "snippet");
    url.searchParams.set("q", query);
    url.searchParams.set("type", "video");
    url.searchParams.set("maxResults", "5");
    url.searchParams.set("regionCode", "JP");
    url.searchParams.set("relevanceLanguage", "ja");
    url.searchParams.set("key", apiKey);

    const resp = await fetch(url);
    if (!resp.ok) return null;
    const data = await resp.json();
    const items: YoutubeSearchItem[] = data?.items ?? [];
    if (items.length === 0) return null;

    const artistNorm = artist.toLowerCase();
    const officialKw = ["official", "公式", "vevo", artistNorm];

    for (const item of items) {
      const channel = (item.snippet?.channelTitle ?? "").toLowerCase();
      const vidTitle = (item.snippet?.title ?? "").toLowerCase();
      const isOfficial = officialKw.some((kw) => kw && (channel.includes(kw) || vidTitle.includes(kw)));
      if (isOfficial) {
        return { id: item.id.videoId, verified: true };
      }
    }
    return { id: items[0].id.videoId, verified: false };
  } catch {
    return null;
  }
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
    // ignoreDuplicates指定時、returnされるのは実際に新規挿入された行のみ
    const { data: inserted, error } = await supabase
      .from("tracks")
      .upsert(rows, { onConflict: "id", ignoreDuplicates: true })
      .select("id, title, artist");

    if (error) throw new Error(error.message);

    const newRows = inserted ?? [];

    // 新規追加分だけSpotify/YouTubeの直リンクを補完（既存曲のAPIクォータ消費を避ける）
    let enriched = 0;
    if (newRows.length > 0) {
      const spotifyToken = await getSpotifyToken();

      await Promise.all(
        newRows.map(async (row) => {
          const updates: Record<string, unknown> = {};

          if (spotifyToken) {
            const spotifyResult = await searchSpotify(spotifyToken, row.title, row.artist);
            if (spotifyResult.url) updates.spotify = spotifyResult.url;
          }

          const yt = await searchYoutube(row.title, row.artist);
          if (yt) {
            updates.youtube = `https://music.youtube.com/watch?v=${yt.id}`;
            updates.youtube_id = yt.id;
            updates.youtube_verified = yt.verified;
          }

          if (Object.keys(updates).length === 0) return;

          const { error: updateError } = await supabase
            .from("tracks")
            .update(updates)
            .eq("id", row.id);

          if (!updateError) enriched++;
        })
      );
    }

    return NextResponse.json({
      message:  "New releases fetched",
      fetched:  entries.length,
      added:    newRows.length,
      enriched,
      sample:   newRows.slice(0, 3).map((r) => `${r.artist} | ${r.title}`),
    });

  } catch (err) {
    console.error("[cron/new-releases]", err);
    return NextResponse.json(
      { error: String(err) },
      { status: 500 }
    );
  }
}
