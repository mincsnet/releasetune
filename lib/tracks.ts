import { createClient } from "@supabase/supabase-js";
import { unstable_cache } from "next/cache";
import { cache } from "react";
import type { Track } from "@/lib/utils";

export type { Track } from "@/lib/utils";

// ── Supabase クライアント ──────────────────────────────────────

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// データ取得キャッシュ（unstable_cache）に付けるタグ。紹介文の公開などで tracks を書き換えたら、
// /api/revalidate からこのタグを消して、期限（最大24時間）を待たずに表示へ反映する
export const TRACKS_CACHE_TAG = "tracks";

// 一覧系のクエリ（日付・アーティスト・検索）で取得する列。
// 楽曲詳細でしか使わない長文（note_long）と出典は含めない（日付ページは1回に最大約90曲を取得するため、
// 長文を含めるとSupabaseの転送量が増える）
const LIST_COLUMNS =
  "id,title,artist,release_date,mmdd,jacket,note,spotify,apple,amazon,youtube,youtube_id,youtube_verified";

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
      const { data, error } = await supabase
        .from("tracks")
        .select(LIST_COLUMNS)
        .eq("mmdd", mmdd)
        .order("release_date", { ascending: false });

      if (error) {
        console.error("getTracksByMmdd error:", error);
        return [];
      }
      return (data ?? []).map(rowToTrack);
    },
    ["tracks-by-mmdd"],
    { revalidate: 3600, tags: [TRACKS_CACHE_TAG] }
  )
);

export const getTrackById = cache(
  unstable_cache(
    async (id: string): Promise<{ track: Track; mmdd: string } | null> => {
      const { data, error } = await supabase
        .from("tracks")
        .select("*")
        .eq("id", id)
        .single();

      if (error || !data) return null;
      return { track: rowToTrack(data), mmdd: String(data.mmdd) };
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
      const { data, error } = await supabase
        .from("tracks")
        .select(LIST_COLUMNS)
        .ilike("artist", name)
        .order("release_date", { ascending: false });

      if (error || !data || data.length === 0) return null;

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

export const getAllArtistNames = cache(
  unstable_cache(
    async (): Promise<string[]> => {
      const { data, error } = await supabase
        .from("tracks")
        .select("artist");

      if (error || !data) return [];
      const set = new Set(data.map((r) => r.artist as string));
      return Array.from(set).sort();
    },
    ["all-artist-names"],
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

      const q = query.trim();

      const { data, error } = await supabase
        .from("tracks")
        .select(LIST_COLUMNS)
        .or(`title.ilike.%${q}%,artist.ilike.%${q}%`)
        .order("release_date", { ascending: false })
        .limit(limit);

      if (error) {
        console.error("searchTracks error:", error);
        return [];
      }

      return (data ?? []).map((row) => ({
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
