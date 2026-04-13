import type { Metadata } from "next";
import { SiteHeader } from "@/components/SiteHeader";
import { SearchPageClient } from "@/components/SearchPageClient";
import { searchTracks } from "@/lib/tracks";

interface Props {
  searchParams: Promise<{ q?: string }>;
}

export const metadata: Metadata = {
  title: "楽曲・アーティスト検索",
  description: "Release Tuneの楽曲・アーティストを検索できます。",
};

export default async function SearchPage({ searchParams }: Props) {
  const { q } = await searchParams;
  const query   = q?.trim() ?? "";
  const results = query ? await searchTracks(query, 50) : [];

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <SiteHeader />
      <SearchPageClient query={query} results={results} />
    </div>
  );
}
