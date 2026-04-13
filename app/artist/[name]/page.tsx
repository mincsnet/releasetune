import { Metadata } from "next";
import { notFound } from "next/navigation";
import { getArtistByName, getDebutDB } from "@/lib/tracks";
import { SiteHeader } from "@/components/SiteHeader";
import { ArtistPageClient } from "@/components/ArtistPageClient";

interface Props {
  params: Promise<{ name: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { name } = await params;
  const artistName = decodeURIComponent(name);
  const artist = await getArtistByName(artistName);
  if (!artist) return {};
  return {
    title: `${artist.name}`,
    description: `${artist.name}のリリース楽曲一覧。${artist.trackCount}曲を収録。`,
    openGraph: {
      title: `${artist.name} — Release Tune`,
      description: `${artist.name}のリリース楽曲一覧。${artist.trackCount}曲を収録。`,
      images: artist.jacket ? [{ url: artist.jacket }] : undefined,
    },
  };
}

export default async function ArtistPage({ params }: Props) {
  const { name } = await params;
  const artistName = decodeURIComponent(name);
  const artist = await getArtistByName(artistName);
  if (!artist) notFound();
  const debutDB = await getDebutDB();
  const debutInfo = debutDB[artist.name] ?? null;
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <SiteHeader />
      <ArtistPageClient artist={artist} debutInfo={debutInfo} />
    </div>
  );
}
