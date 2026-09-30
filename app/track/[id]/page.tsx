import { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTrackById, getTracksByMmdd, parseMmdd, yearsAgo, formatDateJa } from "@/lib/tracks";
import { SiteHeader } from "@/components/SiteHeader";
import { TrackDetailClient } from "@/components/TrackDetailClient";
import { socialTitle } from "@/lib/utils";

interface Props {
  params: Promise<{ id: string }>;
}

export const revalidate = 86400;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const result = await getTrackById(id);
  if (!result) return {};

  const { track } = result;
  const years = yearsAgo(track.releaseDate);
  const title = `${track.title} — ${track.artist}`;
  // シェア時のカードに出るタイトルは、カード画像・シェア文と揃えて「 - Single」を外す
  const socialCardTitle = `${socialTitle(track.title)} — ${track.artist}`;
  const description = track.note
    ? track.note.slice(0, 120)
    : `${formatDateJa(track.releaseDate)}リリース${years > 0 ? `（${years}年前）` : ""}。${track.artist}の楽曲「${track.title}」。`;

  // カード画像は同じフォルダの opengraph-image.tsx が生成し、og:image と twitter:image の両方に自動で出力される
  return {
    title,
    description,
    openGraph: {
      title: socialCardTitle,
      description,
      url: `https://releasetune.com/track/${id}`,
      type: "music.song",
    },
    twitter: {
      card: "summary_large_image",
      title: socialCardTitle,
      description,
    },
    alternates: {
      canonical: `https://releasetune.com/track/${id}`,
    },
  };
}

export default async function TrackPage({ params }: Props) {
  const { id } = await params;
  const result = await getTrackById(id);
  if (!result) notFound();

  const { track, mmdd } = result;
  const { month, day } = parseMmdd(mmdd);

  // 同じ日の他の楽曲
  const allTracks = await getTracksByMmdd(mmdd);
  const siblings = allTracks
    .filter((t) => t.id !== track.id)
    .sort((a, b) => b.releaseDate.localeCompare(a.releaseDate));

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <SiteHeader />
      <TrackDetailClient
        track={track}
        mmdd={mmdd}
        month={month}
        day={day}
        siblings={siblings}
      />
    </div>
  );
}
