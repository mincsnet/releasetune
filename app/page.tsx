import { getTracksByMmdd } from "@/lib/tracks";
import { SiteHeader } from "@/components/SiteHeader";
import { DatePageClient } from "@/components/DatePageClient";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getTodayJST() {
  const now = new Date(
    new Date().toLocaleString("en-US", { timeZone: "Asia/Tokyo" })
  );
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${m}-${d}`;
}

export default async function HomePage() {
  const mmdd = getTodayJST();
  const tracks = await getTracksByMmdd(mmdd);
  const sorted = [...tracks].sort((a, b) =>
    b.releaseDate.localeCompare(a.releaseDate)
  );

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <SiteHeader />
      <DatePageClient mmdd={mmdd} tracks={sorted} today={mmdd} />
    </div>
  );
}
