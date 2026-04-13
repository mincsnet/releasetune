import { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTracksByMmdd, parseMmdd, getTodayMmdd, getDebutsByMmdd } from "@/lib/tracks";
import { SiteHeader } from "@/components/SiteHeader";
import { DatePageClient } from "@/components/DatePageClient";

interface Props {
  params: Promise<{ mmdd: string }>;
}

// MM-DD のバリデーション
function isValidMmdd(mmdd: string): boolean {
  if (!/^\d{2}-\d{2}$/.test(mmdd)) return false;
  const [m, d] = mmdd.split("-").map(Number);
  if (m < 1 || m > 12) return false;
  if (d < 1 || d > 31) return false;
  return true;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { mmdd } = await params;
  if (!isValidMmdd(mmdd)) return {};
  const { month, day } = parseMmdd(mmdd);
  const tracks = await getTracksByMmdd(mmdd);
  const title = `${month}月${day}日のリリース楽曲`;
  const description =
    tracks.length > 0
      ? `${month}月${day}日にリリースされた${tracks.length}曲をご紹介。${tracks
          .slice(0, 3)
          .map((t) => `${t.artist}「${t.title}」`)
          .join("、")}など。`
      : `${month}月${day}日にリリースされた楽曲を年代を超えてご紹介します。`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://releasetune.com/date/${mmdd}`,
    },
    alternates: {
      canonical: `https://releasetune.com/date/${mmdd}`,
    },
  };
}

export default async function DatePage({ params }: Props) {
  const { mmdd } = await params;

  if (!isValidMmdd(mmdd)) notFound();

  const tracks = await getTracksByMmdd(mmdd);
  const sorted = [...tracks].sort((a, b) =>
    b.releaseDate.localeCompare(a.releaseDate)
  );
  const today = getTodayMmdd();
  const debuts = await getDebutsByMmdd(mmdd);

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <SiteHeader />
      <DatePageClient
        mmdd={mmdd}
        tracks={sorted}
        today={today}
        debuts={debuts}
      />
    </div>
  );
}
