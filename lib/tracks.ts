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
