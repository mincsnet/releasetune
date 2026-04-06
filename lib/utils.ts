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

export function parseMmdd(mmdd: string): { month: number; day: number } {
  const [m, d] = mmdd.split("-").map(Number);
  return { month: m, day: d };
}
