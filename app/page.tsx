import { redirect } from "next/navigation";
import { getTodayMmdd } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default function HomePage() {
  const today = getTodayMmdd();
  redirect(`/date/${today}`);
}
