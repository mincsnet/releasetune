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

// ── デビュー日関連 ────────────────────────────────────────────

export interface DebutInfo {
  artist: string;
  debutDate: string;   // YYYY-MM-DD
  debutTrack: string;
  verified: boolean;
}

let _debutCache: Record<string, DebutInfo> | null = null;

export async function getDebutDB(): Promise<Record<string, DebutInfo>> {
  if (_debutCache) return _debutCache;
  const filePath = path.join(process.cwd(), "debut_artists.csv");
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    const lines = raw.trim().split("\n");
    const header = lines[0].split(",");
    const result: Record<string, DebutInfo> = {};
    for (const line of lines.slice(1)) {
      const cols = line.split(",");
      const row: Record<string, string> = {};
      header.forEach((h, i) => { row[h.trim()] = (cols[i] ?? "").trim(); });
      if (row.artist && row.debut_date) {
        result[row.artist] = {
          artist: row.artist,
          debutDate: row.debut_date,
          debutTrack: row.debut_track ?? "",
          verified: row.verified === "true",
        };
      }
    }
    _debutCache = result;
    return result;
  } catch {
    // ファイルがなければ空を返す
    _debutCache = {};
    return {};
  }
}

/**
 * 指定MM-DDにデビューしたアーティスト情報を返す
 * tracks.json の楽曲と照合してデビュー曲も特定する
 */
export async function getDebutsByMmdd(
  mmdd: string
): Promise<(DebutInfo & { track?: Track })[]> {
  const debutDB = await getDebutDB();
  const tracksDB = await getTracksDB();
  const tracksOnDate = tracksDB[mmdd] ?? [];

  const results: (DebutInfo & { track?: Track })[] = [];

  for (const info of Object.values(debutDB)) {
    if (!info.debutDate) continue;
    // MM-DD が一致するか確認（YYYY-MM-DD の 6文字目以降）
    const debutMmdd = info.debutDate.slice(5); // "MM-DD"
    if (debutMmdd !== mmdd) continue;

    // その日の楽曲と照合（デビュー曲があれば添付）
    const matchedTrack = tracksOnDate.find(
      (t) => t.artist.toLowerCase() === info.artist.toLowerCase()
    );

    results.push({ ...info, track: matchedTrack });
  }

  return results;
}
