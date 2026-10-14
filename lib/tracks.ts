import { unstable_cache } from "next/cache";
import { cache } from "react";
import type { Track } from "@/lib/utils";

export type { Track } from "@/lib/utils";

// ── データの取得先（ヘテムル） ─────────────────────────────────
// データはヘテムルの MySQL にある。外部から直接つなげないため、ヘテムル上の読み取り専用 API
// （heteml/public/api/tracks.php → heteml/src/tracks.php）から取得する。問い合わせの中身（取得する列、
// 並び順、最大1000件など）は heteml/src/tracks.php にある。
// 失敗したら例外にする（空の結果を返すと、それが unstable_cache に最大24時間残ってしまうため）

async function fetchTracks<T>(fn: "by_mmdd" | "by_id" | "by_artist" | "search", arg: string, limit?: number): Promise<T> {
  const res = await fetch(`${process.env.HETEML_API_URL}/api/tracks.php`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.HETEML_READ_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ fn, arg, limit }),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`tracks API ${fn}(${arg}) failed: ${res.status} ${(await res.text()).slice(0, 200)}`);
  }
  return res.json();
}

// データ取得キャッシュ（unstable_cache）に付けるタグ。紹介文の公開などで tracks を書き換えたら、
// /api/revalidate からこのタグを消して、期限（最大24時間）を待たずに表示へ反映する
export const TRACKS_CACHE_TAG = "tracks";

// ── DB行 → Track 型変換 ───────────────────────────────────────

function rowToTrack(row: Record<string, unknown>): Track {
  return {
    id:          String(row.id),
    title:       String(row.title || ""),
    artist:      String(row.artist || ""),
    releaseDate: String(row.release_date || ""),
    jacket:      (row.jacket as string) || undefined,
    note:        (row.note as string) || undefined,
    noteLong:    (row.note_long as string) || undefined,
    noteSource:  row.note_source_url
      ? { title: String(row.note_source_title || ""), url: String(row.note_source_url) }
      : undefined,
    links: {
      spotify:         (row.spotify as string) || undefined,
      apple:           (row.apple as string) || undefined,
      amazon:          (row.amazon as string) || undefined,
      youtube:         (row.youtube as string) || undefined,
      youtubeId:       (row.youtube_id as string) || undefined,
      youtubeVerified: (row.youtube_verified as boolean) || false,
    },
  };
}

// ── 基本クエリ ─────────────────────────────────────────────────

export const getTracksByMmdd = cache(
  unstable_cache(
    async (mmdd: string): Promise<Track[]> => {
      const rows = await fetchTracks<Record<string, unknown>[]>("by_mmdd", mmdd);
      return rows.map(rowToTrack);
    },
    ["tracks-by-mmdd"],
    { revalidate: 3600, tags: [TRACKS_CACHE_TAG] }
  )
);

export const getTrackById = cache(
  unstable_cache(
    async (id: string): Promise<{ track: Track; mmdd: string } | null> => {
      const row = await fetchTracks<Record<string, unknown> | null>("by_id", id);
      if (!row) return null;
      return { track: rowToTrack(row), mmdd: String(row.mmdd) };
    },
    ["track-by-id"],
    { revalidate: 86400, tags: [TRACKS_CACHE_TAG] }
  )
);

// ── アーティスト関連 ──────────────────────────────────────────

export interface ArtistSummary {
  name: string;
  trackCount: number;
  jacket: string;
  tracks: (Track & { mmdd: string })[];
}

export const getArtistByName = cache(
  unstable_cache(
    async (name: string): Promise<ArtistSummary | null> => {
      const data = await fetchTracks<Record<string, unknown>[]>("by_artist", name);
      if (data.length === 0) return null;

      const tracks = data.map((row) => ({
        ...rowToTrack(row),
        mmdd: String(row.mmdd),
      }));

      const jacket = tracks.find((t) => t.jacket)?.jacket ?? "";

      return {
        name,
        trackCount: tracks.length,
        jacket,
        tracks,
      };
    },
    ["artist-by-name"],
    { revalidate: 86400, tags: [TRACKS_CACHE_TAG] }
  )
);

// ── 自由検索 ──────────────────────────────────────────────────

export interface SearchResult extends Track {
  mmdd: string;
}

export const searchTracks = cache(
  unstable_cache(
    async (query: string, limit = 50): Promise<SearchResult[]> => {
      if (!query.trim()) return [];

      const data = await fetchTracks<Record<string, unknown>[]>("search", query.trim(), limit);

      return data.map((row) => ({
        ...rowToTrack(row),
        mmdd: String(row.mmdd),
      }));
    },
    ["search-tracks"],
    { revalidate: 3600, tags: [TRACKS_CACHE_TAG] }
  )
);

// ── デビュー日関連 ────────────────────────────────────────────

import path from "path";
import { promises as fs } from "fs";

export interface DebutInfo {
  artist: string;
  debutDate: string;
  debutTrack: string;
  verified: boolean;
}

let _debutCache: Record<string, DebutInfo> | null = null;

export async function getDebutDB(): Promise<Record<string, DebutInfo>> {
  if (_debutCache) return _debutCache;
  const filePath = path.join(process.cwd(), "debut_artists.csv");
  try {
    const raw   = await fs.readFile(filePath, "utf-8");
    const lines = raw.trim().split("\n");
    const header = lines[0].split(",");
    const result: Record<string, DebutInfo> = {};
    for (const line of lines.slice(1)) {
      const cols = line.split(",");
      const row: Record<string, string> = {};
      header.forEach((h, i) => { row[h.trim()] = (cols[i] ?? "").trim(); });
      if (row.artist && row.debut_date) {
        result[row.artist] = {
          artist:     row.artist,
          debutDate:  row.debut_date,
          debutTrack: row.debut_track ?? "",
          verified:   row.verified === "true",
        };
      }
    }
    _debutCache = result;
    return result;
  } catch {
    _debutCache = {};
    return {};
  }
}

export async function getDebutsByMmdd(
  mmdd: string
): Promise<(DebutInfo & { track?: Track })[]> {
  const debutDB = await getDebutDB();
  const tracksOnDate = await getTracksByMmdd(mmdd);
  const results: (DebutInfo & { track?: Track })[] = [];

  for (const info of Object.values(debutDB)) {
    if (!info.debutDate) continue;
    const debutMmdd = info.debutDate.slice(5);
    if (debutMmdd !== mmdd) continue;
    const matchedTrack = tracksOnDate.find(
      (t) => t.artist.toLowerCase() === info.artist.toLowerCase()
    );
    results.push({ ...info, track: matchedTrack });
  }
  return results;
}

// ── ユーティリティ re-export ──────────────────────────────────

export { yearsAgo, formatDateJa, parseMmdd, getTodayMmdd } from "@/lib/utils";
