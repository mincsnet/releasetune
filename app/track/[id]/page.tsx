import { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTrackById, getTracksByMmdd, parseMmdd, yearsAgo, formatDateJa } from "@/lib/tracks";
import { SiteHeader } from "@/components/SiteHeader";
import { TrackDetailClient } from "@/components/TrackDetailClient";

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const result = await getTrackById(id);
  if (!result) return {};

  const { track } = result;
  const years = yearsAgo(track.releaseDate);
  const title = `${track.title} — ${track.artist}`;
  const description = track.note
    ? track.note.slice(0, 120)
    : `${formatDateJa(track.releaseDate)}リリース${years > 0 ? `（${years}年前）` : ""}。${track.artist}の楽曲「${track.title}」。`;

  const ogImage = track.jacket
    ? [{ url: track.jacket, width: 600, height: 600, alt: track.title }]
    : undefined;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://releasetune.com/track/${id}`,
      images: ogImage,
      type: "music.song",
    },
    twitter: {
      card: track.jacket ? "summary_large_image" : "summary",
      title,
      description,
      images: track.jacket ? [track.jacket] : undefined,
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
