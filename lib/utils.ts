// Track 型もここで定義（クライアントコンポーネントが安全に import できる）
export interface Track {
  id: string;
  title: string;
  artist: string;
  releaseDate: string; // "YYYY-MM-DD"
  jacket?: string;
  note?: string;
  links?: {
    spotify?: string;
    apple?: string;
    amazon?: string;
    youtube?: string;
    youtubeId?: string;
    youtubeVerified?: boolean;
  };
}

export function getTodayMmdd(): string {
  const now = new Date();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${m}-${d}`;
}

export function yearsAgo(releaseDate: string): number {
  const year = parseInt(releaseDate.split("-")[0]);
  return new Date().getFullYear() - year;
}

export function formatDateJa(releaseDate: string): string {
  const [y, m, d] = releaseDate.split("-");
  return `${y}年${parseInt(m)}月${parseInt(d)}日`;
}

// SNS（シェア文・カード画像）用の曲名。Apple Music が付ける末尾の「 - Single」は不要なので外す
// （「 - EP」は作品の種類を表すので残す）
export function socialTitle(title: string): string {
  return title.replace(/ - Single$/, "");
}

// アーティスト名のハッシュタグ（#なし）。記号・空白を除いて作る。
// 共演名義（「A & B」「A feat. B」など）は1つのタグにすると別の言葉になるので作らない
export function artistHashtag(artist: string): string | null {
  if (/[&＆、,，×\/／]| x |feat\.|featuring/i.test(artist)) return null;
  const tag = artist.replace(/[^\p{L}\p{M}\p{N}_]/gu, "");
  // 数字だけのタグはXでタグとして扱われない
  return /\p{L}/u.test(tag) ? tag : null;
}

export function parseMmdd(mmdd: string): { month: number; day: number } {
  const [m, d] = mmdd.split("-").map(Number);
  return { month: m, day: d };
}
