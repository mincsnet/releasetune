import path from "path";
import { promises as fs } from "fs";
import type { Track } from "@/lib/utils";

export type { Track } from "@/lib/utils";

// MM-DD → Track[]
export type TracksDB = Record<string, Track[]>;

let _cache: TracksDB | null = null;

export async function getTracksDB(): Promise<TracksDB> {
  if (_cache) return _cache;
  const filePath = path.join(process.cwd(), "data", "tracks.json");
  const raw = await fs.readFile(filePath, "utf-8");
  _cache = JSON.parse(raw) as TracksDB;
  return _cache;
}

export async function getTracksByMmdd(mmdd: string): Promise<Track[]> {
  const db = await getTracksDB();
  return db[mmdd] ?? [];
}

export async function getTrackById(
  id: string
): Promise<{ track: Track; mmdd: string } | null> {
  const db = await getTracksDB();
  for (const [mmdd, tracks] of Object.entries(db)) {
    const track = tracks.find((t) => t.id === id);
    if (track) return { track, mmdd };
  }
  return null;
}

// 共通ユーティリティ re-export
export { yearsAgo, formatDateJa, parseMmdd, getTodayMmdd } from "@/lib/utils";

// ── アーティスト関連 ──────────────────────────────────────────

export interface ArtistSummary {
  name: string;
  trackCount: number;
  jacket: string;         // 代表曲のジャケット（最新曲）
  tracks: (Track & { mmdd: string })[];
}

export async function getArtistByName(
  name: string
): Promise<ArtistSummary | null> {
  const db = await getTracksDB();
  const nameNorm = name.toLowerCase();

  const matched: (Track & { mmdd: string })[] = [];

  for (const [mmdd, tracks] of Object.entries(db)) {
    for (const track of tracks) {
      if (track.artist.toLowerCase() === nameNorm) {
        matched.push({ ...track, mmdd });
      }
    }
  }

  if (matched.length === 0) return null;

  // 新しい順にソート
  matched.sort((a, b) => b.releaseDate.localeCompare(a.releaseDate));

  // 代表ジャケット：ジャケットありの最新曲
  const jacket =
    matched.find((t) => t.jacket)?.jacket ?? "";

  return {
    name,
    trackCount: matched.length,
    jacket,
    tracks: matched,
  };
}

export async function getAllArtistNames(): Promise<string[]> {
  const db = await getTracksDB();
  const set = new Set<string>();
  for (const tracks of Object.values(db)) {
    for (const t of tracks) {
      if (t.artist) set.add(t.artist);
    }
  }
  return Array.from(set).sort();
}
